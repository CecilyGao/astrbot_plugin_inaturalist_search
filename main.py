import aiohttp
import logging
from typing import Optional, List, Dict, Any
import traceback

from astrbot.api.all import (
    Star, Context, register,
    AstrMessageEvent,
    MessageEventResult, llm_tool
)
from astrbot.api.event import filter
from astrbot.api.message_components import Image, Plain

# ==============================
# HTML 模板（与之前相同，此处略）
# ==============================
TAXON_TEMPLATE = """..."""  # 请保留原有的模板内容
OBSERVATIONS_TEMPLATE = """..."""  # 请保留原有的模板内容

@register(
    "astrbot_plugin_inaturalist_search",
    "CecilyGao",
    "一个基于iNaturalist API的自然观察数据查询插件，支持分类单元信息和观察记录的关键词搜索",
    "1.0.0",
    "https://github.com/CecilyGao/astrbot_plugin_inaturalist_search"
)
class InaturalistPlugin(Star):
    def __init__(self, context: Context, config: dict = None):
        super().__init__(context)
        self.logger = logging.getLogger("InaturalistPlugin")
        self.logger.setLevel(logging.DEBUG)
        self.config = config or {}

        self.inat_user = self.config.get("inat_user", "")
        self.inat_password = self.config.get("inat_password", "")

        self.send_mode = self.config.get("send_mode", "text")
        self.taxon_send_mode = self.config.get("taxon_send_mode", "")
        if not self.taxon_send_mode:
            self.taxon_send_mode = self.send_mode
        self.observations_send_mode = self.config.get("observations_send_mode", "")
        if not self.observations_send_mode:
            self.observations_send_mode = self.send_mode

        self.default_limit = self.config.get("default_observation_limit", 5)
        try:
            self.default_limit = int(self.default_limit)
        except (ValueError, TypeError):
            self.default_limit = 5

        self.logger.debug(f"InaturalistPlugin initialized. "
                          f"taxon_send_mode={self.taxon_send_mode}, "
                          f"observations_send_mode={self.observations_send_mode}, "
                          f"default_limit={self.default_limit}")

    # =============================
    # 单一命令入口
    # =============================
    @filter.command("ina")
    async def ina(self, event: AstrMessageEvent):
        full_text = event.message_str.strip()
        parts = full_text.split()
        if len(parts) < 2:
            yield event.plain_result("请提供子命令，例如：ina taxon <关键词>。输入 'ina help' 查看帮助。")
            return

        subcmd = parts[1].lower()
        args = parts[2:] if len(parts) > 2 else []

        if subcmd in ['taxon', 't']:
            async for result in self._handle_taxon(event, args):
                yield result
        elif subcmd in ['observations', 'obs']:
            async for result in self._handle_observations(event, args):
                yield result
        elif subcmd == 'help':
            async for result in self._handle_help(event):
                yield result
        else:
            yield event.plain_result(f"未知子命令: {subcmd}。输入 'ina help' 查看帮助。")

    async def _handle_taxon(self, event: AstrMessageEvent, args: List[str]):
        if not args:
            yield event.plain_result("请提供要查询的关键词（例如：ina taxon 大熊猫）。")
            return

        keyword = " ".join(args)
        self.logger.info(f"User called ina taxon with keyword={keyword}")

        taxon = await self.search_taxon(keyword)
        if taxon is None:
            yield event.plain_result(f"未找到与 [{keyword}] 匹配的分类单元。")
            return

        info = {
            "id": taxon.get("id"),
            "name": taxon.get("name", "未知"),
            "preferred_common_name": taxon.get("preferred_common_name"),
            "rank": taxon.get("rank", "未知"),
            "iconic_taxon_name": taxon.get("iconic_taxon_name"),
            "parent_name": taxon.get("parent", {}).get("name") if taxon.get("parent") else None,
            "observations_count": taxon.get("observations_count", 0),
            "default_photo_url": None
        }
        if taxon.get("default_photo"):
            photo = taxon["default_photo"]
            if photo.get("url"):
                info["default_photo_url"] = photo["url"].replace("square", "medium")

        if self.taxon_send_mode == "image":
            img_url = await self.render_taxon_info(info)
            # 参考视频插件，使用 chain_result 发送图片
            yield event.chain_result([Image.fromURL(img_url)])
        else:
            text = (
                f"🌿 iNaturalist 分类单元信息：\n"
                f"关键词：{keyword}\n"
                f"学名：{info['name']}\n"
                f"常用名：{info['preferred_common_name'] or '无'}\n"
                f"分类等级：{info['rank']}\n"
                f"Iconic 分类：{info['iconic_taxon_name'] or '无'}\n"
                f"父分类：{info['parent_name'] or '无'}\n"
                f"观察数量：{info['observations_count']}\n"
                f"iNaturalist ID：{info['id']}\n"
                f"更多信息：https://www.inaturalist.org/taxa/{info['id']}"
            )
            yield event.plain_result(text)

    async def _handle_observations(self, event: AstrMessageEvent, args: List[str]):
        if not args:
            yield event.plain_result("请提供搜索关键词（例如：ina observations 10 啄木鸟）。")
            return

        limit = self.default_limit
        keyword_parts = args
        if args and args[0].isdigit():
            limit = int(args[0])
            keyword_parts = args[1:]

        if not keyword_parts:
            yield event.plain_result("请提供有效的关键词。")
            return

        keyword = " ".join(keyword_parts)
        self.logger.info(f"User called ina observations with keyword={keyword}, limit={limit}")

        total_count, observations = await self.search_observations(keyword, limit=limit)
        if total_count is None:
            yield event.plain_result(f"搜索 [{keyword}] 的观察记录时出错。")
            return

        samples = []
        for obs in observations:
            sample = {
                "id": obs.get("id"),
                "place_guess": obs.get("place_guess"),
                "observed_on": obs.get("observed_on"),
                "link": f"https://www.inaturalist.org/observations/{obs.get('id')}",
                "photo_url": None
            }
            if obs.get("photos") and len(obs["photos"]) > 0:
                photo = obs["photos"][0]
                if photo.get("url"):
                    sample["photo_url"] = photo["url"].replace("square", "medium")
            samples.append(sample)

        if self.observations_send_mode == "image":
            img_url = await self.render_observations_info(
                keyword=keyword,
                total_count=total_count,
                samples=samples
            )
            # 参考视频插件，使用 chain_result 发送图片
            yield event.chain_result([Image.fromURL(img_url)])
        else:
            yield event.plain_result(f"🌍 iNaturalist 观察记录搜索：\n关键词：{keyword}\n总记录数：{total_count} 条")
            for sample in samples:
                text = f"📍 地点：{sample['place_guess'] or '未知'}\n📅 日期：{sample['observed_on'] or '未知'}\n🔗 链接：{sample['link']}"
                if sample.get('photo_url'):
                    chain = [Image.fromURL(sample['photo_url']), Plain(text)]
                    yield event.chain_result(chain)
                else:
                    yield event.plain_result(text)

    async def _handle_help(self, event: AstrMessageEvent):
        help_text = (
            "🌿 iNaturalist 自然观察数据查询插件 v1.0.0\n"
            "命令列表：\n"
            "ina taxon <关键词> \n"
            "» 查询分类单元信息（可缩写为ina t）\n"
            "ina observations <数量> <关键词> \n"
            "» 搜索观察记录，显示总数和样本（可缩写为ina obs）\n"
            "ina help \n"
            "» 显示本帮助\n"
            "示例：\n"
            "ina taxon 大熊猫\n"
            "ina obs 10 啄木鸟\n"
            "数据来源：iNaturalist.org"
        )
        yield event.plain_result(help_text)

    # =============================
    # LLM 工具
    # =============================
    @llm_tool(name="get_inaturalist_taxon")
    async def get_inaturalist_taxon_tool(self, event: AstrMessageEvent, keyword: str) -> MessageEventResult:
        taxon = await self.search_taxon(keyword)
        if not taxon:
            yield event.plain_result(f"未找到分类单元 [{keyword}] 的信息。")
            return

        info = {
            "id": taxon.get("id"),
            "name": taxon.get("name", "未知"),
            "preferred_common_name": taxon.get("preferred_common_name"),
            "rank": taxon.get("rank", "未知"),
            "iconic_taxon_name": taxon.get("iconic_taxon_name"),
            "parent_name": taxon.get("parent", {}).get("name") if taxon.get("parent") else None,
            "observations_count": taxon.get("observations_count", 0),
            "default_photo_url": None
        }
        if taxon.get("default_photo") and taxon["default_photo"].get("url"):
            info["default_photo_url"] = taxon["default_photo"]["url"].replace("square", "medium")

        if self.taxon_send_mode == "image":
            img_url = await self.render_taxon_info(info)
            yield event.chain_result([Image.fromURL(img_url)])
        else:
            text = (
                f"🌿 iNaturalist 分类单元信息：\n"
                f"关键词：{keyword}\n"
                f"学名：{info['name']}\n"
                f"常用名：{info['preferred_common_name'] or '无'}\n"
                f"等级：{info['rank']}\n"
                f"Iconic 分类：{info['iconic_taxon_name'] or '无'}\n"
                f"观察数量：{info['observations_count']}\n"
                f"iNaturalist ID：{info['id']}\n"
                f"链接：https://www.inaturalist.org/taxa/{info['id']}"
            )
            yield event.plain_result(text)

    @llm_tool(name="get_inaturalist_observations")
    async def get_inaturalist_observations_tool(self, event: AstrMessageEvent, keyword: str) -> MessageEventResult:
        total_count, observations = await self.search_observations(keyword, limit=self.default_limit)
        if total_count is None:
            yield event.plain_result(f"搜索 [{keyword}] 的观察记录时出错。")
            return

        samples = []
        for obs in observations:
            sample = {
                "id": obs.get("id"),
                "place_guess": obs.get("place_guess"),
                "observed_on": obs.get("observed_on"),
                "link": f"https://www.inaturalist.org/observations/{obs.get('id')}",
                "photo_url": None
            }
            if obs.get("photos") and len(obs["photos"]) > 0:
                photo = obs["photos"][0]
                if photo.get("url"):
                    sample["photo_url"] = photo["url"].replace("square", "medium")
            samples.append(sample)

        if self.observations_send_mode == "image":
            img_url = await self.render_observations_info(keyword, total_count, samples)
            yield event.chain_result([Image.fromURL(img_url)])
        else:
            yield event.plain_result(f"🌍 iNaturalist 观察记录搜索：关键词“{keyword}”，共 {total_count} 条记录。")
            for sample in samples:
                text = f"📍 地点：{sample['place_guess'] or '未知'}\n📅 日期：{sample['observed_on'] or '未知'}\n🔗 链接：{sample['link']}"
                if sample.get('photo_url'):
                    chain = [Image.fromURL(sample['photo_url']), Plain(text)]
                    yield event.chain_result(chain)
                else:
                    yield event.plain_result(text)

    # =============================
    # iNaturalist API 调用核心
    # =============================
    async def search_taxon(self, keyword: str) -> Optional[Dict[str, Any]]:
        self.logger.debug(f"search_taxon: {keyword}")
        url = "https://api.inaturalist.org/v1/taxa"
        params = {
            "q": keyword,
            "per_page": 1,
            "order_by": "observations_count",
            "order": "desc"
        }
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, params=params, timeout=10) as resp:
                    self.logger.debug(f"Taxa search response status: {resp.status}")
                    if resp.status == 200:
                        data = await resp.json()
                        if data.get("total_results", 0) > 0 and data.get("results"):
                            return data["results"][0]
                        else:
                            return None
                    else:
                        self.logger.error(f"Taxa search HTTP {resp.status}")
                        return None
        except Exception as e:
            self.logger.error(f"search_taxon error: {e}\n{traceback.format_exc()}")
            return None

    async def search_observations(self, keyword: str, limit: int = 5) -> tuple[Optional[int], List[Dict]]:
        self.logger.debug(f"search_observations: keyword={keyword}, limit={limit}")
        url = "https://api.inaturalist.org/v1/observations"
        params = {
            "q": keyword,
            "per_page": limit,
            "order_by": "observed_on",
            "order": "desc"
        }
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, params=params, timeout=10) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        total = data.get("total_results", 0)
                        results = data.get("results", [])
                        self.logger.debug(f"Found {total} total, returning {len(results)} samples")
                        return total, results
                    else:
                        self.logger.error(f"Observations search HTTP {resp.status}")
                        return None, []
        except Exception as e:
            self.logger.error(f"search_observations error: {e}\n{traceback.format_exc()}")
            return None, []

    # =============================
    # 渲染图片（返回图片 URL）
    # =============================
    async def render_taxon_info(self, info: dict) -> str:
        self.logger.debug(f"Rendering taxon info: {info}")
        url = await self.html_render(
            TAXON_TEMPLATE,
            info,
            return_url=True
        )
        return url

    async def render_observations_info(self, keyword: str, total_count: int, samples: List[dict]) -> str:
        self.logger.debug(f"Rendering observations for keyword={keyword}, count={total_count}")
        data = {
            "keyword": keyword,
            "totalCount": total_count,
            "samples": samples
        }
        url = await self.html_render(
            OBSERVATIONS_TEMPLATE,
            data,
            return_url=True
        )
        return url