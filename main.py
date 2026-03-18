import aiohttp
import logging
import random
import traceback
from typing import Optional, List, Dict, Any

from astrbot.api.all import (
    Star, Context, register,
    AstrMessageEvent,
    MessageEventResult, llm_tool
)
from astrbot.api.event import filter
from astrbot.api.message_components import Image, Plain, Target
from astrbot.core.platform.sources.aiocqhttp.aiocqhttp_message_event import (
    AiocqhttpMessageEvent,
)
from astrbot.core import logger

# ==============================
# HTML 模板（用于图片渲染）
# ==============================

TAXON_TEMPLATE = """
<html>
<head>
  <meta charset="UTF-8"/>
  <style>
    html, body {
      margin: 0;
      padding: 0;
      width: 1280px;
      height: 720px;
      background-color: #f5f5f5;
    }
    .container {
      width: 100%;
      height: 100%;
      padding: 20px;
      display: flex;
      flex-direction: column;
      background-color: #fff;
      color: #333;
      font-family: 'Segoe UI', sans-serif;
      border: 1px solid #ddd;
      border-radius: 12px;
      box-sizing: border-box;
    }
    h2 {
      margin: 0 0 16px 0;
      color: #2c3e50;
      text-align: center;
      font-size: 40px;
      border-bottom: 2px solid #74ac00;
      padding-bottom: 10px;
    }
    .taxon-img {
      text-align: center;
      margin: 10px 0;
    }
    .taxon-img img {
      max-width: 300px;
      max-height: 200px;
      border-radius: 8px;
      border: 1px solid #ddd;
    }
    .info-grid {
      display: grid;
      grid-template-columns: repeat(2, 1fr);
      gap: 12px;
      font-size: 24px;
    }
    .info-item {
      padding: 8px;
      background: #f9f9f9;
      border-radius: 8px;
    }
    .label {
      font-weight: bold;
      color: #2c3e50;
    }
    .value {
      color: #74ac00;
      margin-left: 8px;
    }
    .common-name {
      background: #e8f5e9;
      padding: 12px;
      border-radius: 8px;
      margin-top: 16px;
      text-align: center;
      font-size: 28px;
      border: 1px dashed #74ac00;
    }
    .source-info {
      margin-top: auto;
      border-top: 1px solid #ddd;
      padding-top: 12px;
      font-size: 18px;
      color: #7f8c8d;
      text-align: right;
    }
  </style>
</head>
<body>
  <div class="container">
    <h2>🌿 iNaturalist 分类单元信息</h2>
    {% if default_photo_url %}
    <div class="taxon-img"><img src="{{ default_photo_url }}" alt="代表照片"/></div>
    {% endif %}
    <div class="info-grid">
      <div class="info-item"><span class="label">学名:</span> <span class="value">{{ name }}</span></div>
      <div class="info-item"><span class="label">常用名:</span> <span class="value">{{ preferred_common_name or '无' }}</span></div>
      <div class="info-item"><span class="label">分类等级:</span> <span class="value">{{ rank }}</span></div>
      <div class="info-item"><span class="label">Iconic 分类:</span> <span class="value">{{ iconic_taxon_name or '无' }}</span></div>
      <div class="info-item"><span class="label">父分类:</span> <span class="value">{{ parent_name or '无' }}</span></div>
      <div class="info-item"><span class="label">观察数量:</span> <span class="value">{{ observations_count }}</span></div>
    </div>
    <div class="common-name">
      <span class="label">iNaturalist ID (taxon_id):</span> <span class="value">{{ id }}</span>
    </div>
    <div class="source-info">
      数据来源: iNaturalist.org 免费API
    </div>
  </div>
</body>
</html>
"""

OBSERVATIONS_TEMPLATE = """
<html>
<head>
  <meta charset="UTF-8"/>
  <style>
    html, body {
      margin: 0;
      padding: 0;
      width: 1280px;
      height: 720px;
      background-color: #f5f5f5;
    }
    .container {
      width: 100%;
      height: 100%;
      padding: 20px;
      display: flex;
      flex-direction: column;
      background-color: #fff;
      color: #333;
      font-family: 'Segoe UI', sans-serif;
      border: 1px solid #ddd;
      border-radius: 12px;
      box-sizing: border-box;
    }
    h2 {
      margin: 0 0 8px 0;
      color: #2c3e50;
      text-align: center;
      font-size: 40px;
      border-bottom: 2px solid #1e90ff;
      padding-bottom: 10px;
    }
    .search-keyword {
      text-align: center;
      font-size: 28px;
      color: #1e90ff;
      margin-bottom: 16px;
      font-weight: bold;
    }
    .count-badge {
      background: #1e90ff;
      color: white;
      font-size: 36px;
      padding: 16px;
      border-radius: 60px;
      text-align: center;
      margin: 16px 0;
      box-shadow: 0 4px 8px rgba(0,0,0,0.1);
    }
    .samples-title {
      font-size: 24px;
      font-weight: bold;
      color: #2c3e50;
      margin-top: 16px;
      margin-bottom: 8px;
    }
    .sample-item {
      background: #ecf0f1;
      margin-bottom: 12px;
      padding: 12px;
      border-radius: 8px;
      font-size: 20px;
      border-left: 5px solid #1e90ff;
      display: flex;
      align-items: center;
    }
    .sample-thumb {
      width: 60px;
      height: 60px;
      margin-right: 12px;
      border-radius: 4px;
      object-fit: cover;
      background: #bdc3c7;
    }
    .sample-details {
      flex: 1;
    }
    .sample-loc {
      font-weight: bold;
    }
    .sample-link {
      word-break: break-all;
      font-size: 16px;
      color: #1e90ff;
      margin-top: 4px;
    }
    .source-info {
      margin-top: auto;
      border-top: 1px solid #ddd;
      padding-top: 12px;
      font-size: 18px;
      color: #7f8c8d;
      text-align: right;
    }
  </style>
</head>
<body>
  <div class="container">
    <h2>🌍 iNaturalist 观察记录</h2>
    <div class="search-keyword">关键词: {{ keyword }}</div>
    <div class="count-badge">总记录数: {{ totalCount }} 条</div>
    {% if samples %}
    <div class="samples-title">📌 样本（共 {{ samples|length }} 条）</div>
    {% for sample in samples %}
    <div class="sample-item">
      {% if sample.photo_url %}
      <img class="sample-thumb" src="{{ sample.photo_url }}" alt="照片"/>
      {% else %}
      <div class="sample-thumb" style="background:#bdc3c7; text-align:center; line-height:60px;">📷</div>
      {% endif %}
      <div class="sample-details">
        <div><span class="sample-loc">📍 地点:</span> {{ sample.place_guess or '未知' }}</div>
        <div><span class="sample-loc">📅 日期:</span> {{ sample.observed_on or '未知' }}</div>
        <div><span class="sample-loc">🔗 链接:</span> <span class="sample-link">{{ sample.link }}</span></div>
      </div>
    </div>
    {% endfor %}
    {% endif %}
    <div class="source-info">
      数据来源: iNaturalist.org 免费API
    </div>
  </div>
</body>
</html>
"""

@register(
    "astrbot_plugin_inaturalist_search",
    "CecilyGao",
    "一个基于iNaturalist API的自然观察数据查询插件，支持分类单元信息和观察记录的关键词搜索，并支持每日随机物种播报",
    "1.1.0",
    "https://github.com/CecilyGao/astrbot_plugin_inaturalist_search"
)
class InaturalistPlugin(Star):
    """
    调用 iNaturalist API 查询分类单元信息和观察记录。
    支持命令：
      ina taxon <关键词>               - 查询分类单元信息（可用 t 缩写）
      ina observations [数量] <关键词>  - 搜索观察记录，显示总数和样本（可用 obs 缩写），数量可前置如：ina obs 10 啄木鸟
      ina help                          - 显示帮助
      gbif daily                        - 手动触发随机物种介绍播报
    也提供LLM工具调用。
    每日随机物种播报：通过 CRON 表达式配置，向白名单中的群/私聊发送随机物种介绍。
    """
    def __init__(self, context: Context, config: dict = None):
        super().__init__(context)
        self.logger = logging.getLogger("InaturalistPlugin")
        self.logger.setLevel(logging.DEBUG)
        self.config = config or {}

        # 认证预留
        self.inat_user = self.config.get("inat_user", "")
        self.inat_password = self.config.get("inat_password", "")

        # 全局发送模式
        self.send_mode = self.config.get("send_mode", "text")
        # 子命令专用发送模式
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

        # 每日播报配置
        self.daily_species_cron = self.config.get("daily_species_cron", "")
        self.daily_species_white_list = self.config.get("daily_species_white_list", [])
        self.daily_job = None
        if self.daily_species_cron:
            self._setup_daily_job()

        self.logger.debug(f"InaturalistPlugin initialized. "
                          f"taxon_send_mode={self.taxon_send_mode}, "
                          f"observations_send_mode={self.observations_send_mode}, "
                          f"default_limit={self.default_limit}, "
                          f"daily_species_cron={self.daily_species_cron}, "
                          f"white_list={self.daily_species_white_list}")

    # =============================
    # 定时任务设置
    # =============================
    def _setup_daily_job(self):
        """注册每日播报定时任务"""
        try:
            job_id = f"{self.__class__.__name__}_daily_species"
            self.daily_job = self.context.scheduler.add_job(
                self._daily_species_job,
                trigger='cron',
                id=job_id,
                replace_existing=True,
                **self._parse_cron(self.daily_species_cron)
            )
            self.logger.info(f"每日物种播报定时任务已设置，CRON: {self.daily_species_cron}")
        except Exception as e:
            self.logger.error(f"设置每日物种播报定时任务失败: {e}")

    def _parse_cron(self, cron_expr: str) -> dict:
        """
        将 CRON 表达式解析为 apscheduler 的 cron 参数
        支持标准 5 位或 6 位 CRON，这里简化为按空格分割
        """
        parts = cron_expr.split()
        # 适配常见的 5 位 (分 时 日 月 周)
        if len(parts) == 5:
            return {
                'minute': parts[0],
                'hour': parts[1],
                'day': parts[2],
                'month': parts[3],
                'day_of_week': parts[4]
            }
        else:
            # 其他情况直接返回原表达式，可能报错
            return {'cron': cron_expr}

    async def terminate(self):
        """插件卸载时移除定时任务"""
        if self.daily_job:
            try:
                self.context.scheduler.remove_job(self.daily_job.id)
                self.logger.info("每日物种播报定时任务已移除")
            except Exception as e:
                self.logger.error(f"移除定时任务失败: {e}")

    # =============================
    # 发送合并转发（参考 multimsg 插件）
    # =============================
    async def _send_forward(self, event: AstrMessageEvent, nodes: list):
        """使用 OneBot API 发送合并转发消息"""
        if not isinstance(event, AiocqhttpMessageEvent):
            # 非 OneBot 平台，无法发送合并转发，降级为逐条发送
            for node in nodes:
                for content in node["data"]["content"]:
                    if content["type"] == "text":
                        yield event.plain_result(content["data"]["text"])
                    elif content["type"] == "image":
                        yield event.image_result(content["data"]["file"])
            return

        payload = {"message": nodes}
        if event.is_private_chat():
            payload["user_id"] = int(event.get_sender_id())
            action = "send_private_forward_msg"
        else:
            payload["group_id"] = int(event.get_group_id())
            action = "send_group_forward_msg"

        try:
            await event.bot.api.call_action(action, **payload)
            event.stop_event()
        except Exception as e:
            logger.error(f"[InaturalistPlugin] 发送合并转发失败: {e}")
            yield event.plain_result("发送合并转发失败，请稍后重试。")

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

    @filter.command("gbif")
    async def gbif(self, event: AstrMessageEvent):
        """手动触发随机物种介绍"""
        full_text = event.message_str.strip()
        parts = full_text.split()
        if len(parts) < 2 or parts[1].lower() != 'daily':
            yield event.plain_result("用法：gbif daily — 手动获取一条随机物种介绍")
            return

        self.logger.info("用户手动触发随机物种介绍")
        # 发送等待提示
        yield event.plain_result("正在获取随机物种信息，请稍候...")

        info = await self._fetch_random_species()
        if not info:
            yield event.plain_result("获取随机物种信息失败，请稍后重试。")
            return

        chain = self._build_species_message(info)
        yield event.chain_result(chain)

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

        # 提取显示信息
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
        # 尝试获取代表照片
        if taxon.get("default_photo"):
            photo = taxon["default_photo"]
            if photo.get("url"):
                # 替换为 medium 尺寸
                info["default_photo_url"] = photo["url"].replace("square", "medium")

        if self.taxon_send_mode == "image":
            img_url = await self.render_taxon_info(info)
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
        # 立即发送安慰语
        yield event.plain_result("正在查询 iNaturalist，请稍候...")

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

        # 处理样本，添加链接和照片
        samples = []
        for obs in observations:
            sample = {
                "id": obs.get("id"),
                "place_guess": obs.get("place_guess"),
                "observed_on": obs.get("observed_on"),
                "link": f"https://www.inaturalist.org/observations/{obs.get('id')}",
                "photo_url": None
            }
            # 取第一张照片的 medium 尺寸
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
            yield event.chain_result([Image.fromURL(img_url)])
        else:
            # 文本模式：构建合并转发节点
            nodes = []
            bot_id = event.get_self_id() or "1000000"
            bot_name = "iNaturalist Bot"

            # 总览节点
            overview_text = f"🌍 iNaturalist 观察记录搜索\n关键词：{keyword}\n总记录数：{total_count} 条"
            nodes.append({
                "type": "node",
                "data": {
                    "user_id": int(bot_id),
                    "nickname": bot_name,
                    "content": [{"type": "text", "data": {"text": overview_text}}]
                }
            })

            # 每条记录的节点
            for sample in samples:
                content = []
                if sample.get('photo_url'):
                    content.append({
                        "type": "image",
                        "data": {"file": sample['photo_url']}
                    })
                content.append({
                    "type": "text",
                    "data": {
                        "text": f"📍 地点：{sample['place_guess'] or '未知'}\n📅 日期：{sample['observed_on'] or '未知'}\n🔗 链接：{sample['link']}"
                    }
                })
                nodes.append({
                    "type": "node",
                    "data": {
                        "user_id": int(bot_id),
                        "nickname": bot_name,
                        "content": content
                    }
                })

            # 发送合并转发
            async for result in self._send_forward(event, nodes):
                yield result

    async def _handle_help(self, event: AstrMessageEvent):
        help_text = (
            "🌿 iNaturalist 自然观察数据查询插件 v1.1.0\n"
            "命令列表：\n"
            "ina taxon <关键词> \n"
            "» 查询分类单元信息（可缩写为ina t）\n"
            "ina observations <数量> <关键词> \n"
            "» 搜索观察记录，显示总数和样本（可缩写为ina obs）\n"
            "ina help \n"
            "» 显示本帮助\n"
            "gbif daily \n"
            "» 手动触发随机物种介绍播报\n"
            "示例：\n"
            "ina taxon 大熊猫\n"
            "ina obs 10 啄木鸟\n"
            "gbif daily\n"
            "数据来源：iNaturalist.org"
        )
        yield event.plain_result(help_text)

    # =============================
    # LLM 工具
    # =============================
    @llm_tool(name="get_inaturalist_taxon")
    async def get_inaturalist_taxon_tool(self, event: AstrMessageEvent, keyword: str) -> MessageEventResult:
        '''查询iNaturalist中的分类单元信息，当用户询问某个物种的分类信息时使用。

        Args:
            keyword (string): 物种关键词，例如 "大熊猫" 或 "Ailuropoda melanoleuca"
        '''
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
        '''查询iNaturalist中与关键词匹配的观察记录，当用户询问某物种的观察记录或分布时使用。

        Args:
            keyword (string): 搜索关键词，例如 "大熊猫" 或 "啄木鸟"
        '''
        # 先发送安慰语
        yield event.plain_result("正在查询 iNaturalist，请稍候...")

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
            # 构建合并转发节点
            nodes = []
            bot_id = event.get_self_id() or "1000000"
            bot_name = "iNaturalist Bot"

            overview_text = f"🌍 iNaturalist 观察记录搜索\n关键词：{keyword}\n总记录数：{total_count} 条"
            nodes.append({
                "type": "node",
                "data": {
                    "user_id": int(bot_id),
                    "nickname": bot_name,
                    "content": [{"type": "text", "data": {"text": overview_text}}]
                }
            })

            for sample in samples:
                content = []
                if sample.get('photo_url'):
                    content.append({
                        "type": "image",
                        "data": {"file": sample['photo_url']}
                    })
                content.append({
                    "type": "text",
                    "data": {
                        "text": f"📍 地点：{sample['place_guess'] or '未知'}\n📅 日期：{sample['observed_on'] or '未知'}\n🔗 链接：{sample['link']}"
                    }
                })
                nodes.append({
                    "type": "node",
                    "data": {
                        "user_id": int(bot_id),
                        "nickname": bot_name,
                        "content": content
                    }
                })

            async for result in self._send_forward(event, nodes):
                yield result

    # =============================
    # iNaturalist API 调用核心
    # =============================
    async def search_taxon(self, keyword: str) -> Optional[Dict[str, Any]]:
        """
        调用 /v1/taxa 接口，搜索分类单元，返回最佳匹配的第一个结果。
        """
        self.logger.debug(f"search_taxon: {keyword}")
        url = "https://api.inaturalist.org/v1/taxa"
        params = {
            "q": keyword,
            "per_page": 1,
            "order_by": "observations_count",  # 按观察数排序，通常更相关
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
        """
        调用 /v1/observations 接口，搜索观察记录。
        返回 (总记录数, 样本列表)
        """
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
        # 为模板中的日期字段做准备
        for s in samples:
            s['date'] = s.get('observed_on') or '未知'
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

    # =============================
    # 每日随机物种相关方法
    # =============================
    async def _fetch_random_species(self) -> Optional[Dict[str, Any]]:
        """
        从 iNaturalist 获取一个随机物种的信息
        返回字典包含：id, name, common_name, description, photo_url, link
        """
        try:
            # 第一步：获取总 taxa 数量
            url = "https://api.inaturalist.org/v1/taxa"
            params = {"per_page": 1}
            async with aiohttp.ClientSession() as session:
                async with session.get(url, params=params, timeout=10) as resp:
                    if resp.status != 200:
                        self.logger.error(f"获取总taxa数量失败: {resp.status}")
                        return None
                    data = await resp.json()
                    total_results = data.get("total_results", 0)
                    if total_results == 0:
                        self.logger.error("总taxa结果为0")
                        return None

            # 随机选择一个页码 (per_page=1 时页数等于总结果数)
            random_page = random.randint(1, total_results)
            params = {"page": random_page, "per_page": 1}
            async with aiohttp.ClientSession() as session:
                async with session.get(url, params=params, timeout=10) as resp:
                    if resp.status != 200:
                        self.logger.error(f"获取随机taxa失败: {resp.status}")
                        return None
                    data = await resp.json()
                    results = data.get("results", [])
                    if not results:
                        self.logger.error("随机taxa结果为空")
                        return None
                    taxon = results[0]

            # 提取信息
            info = {
                "id": taxon.get("id"),
                "name": taxon.get("name", "未知学名"),
                "common_name": taxon.get("preferred_common_name") or "无常用名",
                "description": "暂无详细介绍。",
                "photo_url": None,
                "link": f"https://www.inaturalist.org/taxa/{taxon.get('id')}"
            }

            # 获取介绍（如果有wikipedia_summary）
            if taxon.get("wikipedia_summary"):
                summary = taxon["wikipedia_summary"]
                if isinstance(summary, dict) and summary.get("description"):
                    info["description"] = summary["description"]

            # 获取图片
            if taxon.get("default_photo") and taxon["default_photo"].get("url"):
                info["photo_url"] = taxon["default_photo"]["url"].replace("square", "medium")

            return info

        except Exception as e:
            self.logger.error(f"获取随机物种失败: {e}\n{traceback.format_exc()}")
            return None

    def _build_species_message(self, info: dict) -> list:
        """
        根据物种信息构建消息链（文本 + 可选图片）
        """
        text = (
            f"🌿 随机物种介绍\n"
            f"学名：{info['name']}\n"
            f"常用名：{info['common_name']}\n"
            f"介绍：{info['description']}\n"
            f"更多信息：{info['link']}"
        )
        chain = [Plain(text)]
        if info.get("photo_url"):
            chain.append(Image.fromURL(info["photo_url"]))
        return chain

    def _parse_umo(self, umo: str) -> tuple:
        """
        解析 UMO 字符串，返回 (platform, msg_type, target_id)
        例如 "default:GroupMessage:921431240" -> ("default", "GroupMessage", "921431240")
        """
        parts = umo.split(':')
        if len(parts) != 3:
            raise ValueError(f"无效的UMO格式: {umo}")
        return parts[0], parts[1], parts[2]

    async def _daily_species_job(self):
        """定时任务：向白名单中所有目标发送随机物种介绍"""
        self.logger.info("开始执行每日物种播报定时任务")
        if not self.daily_species_white_list:
            self.logger.warning("白名单为空，跳过播报")
            return

        info = await self._fetch_random_species()
        if not info:
            self.logger.error("获取随机物种信息失败，本次播报取消")
            return

        chain = self._build_species_message(info)

        for umo in self.daily_species_white_list:
            try:
                platform_name, msg_type, target_id = self._parse_umo(umo)
                # 根据消息类型确定 target_type
                if msg_type == "GroupMessage":
                    target_type = "group"
                elif msg_type == "FriendMessage":
                    target_type = "private"
                else:
                    self.logger.error(f"未知的消息类型: {msg_type}，跳过 {umo}")
                    continue

                platform = self.context.get_platform(platform_name)
                if not platform:
                    self.logger.error(f"平台 {platform_name} 不存在，跳过 {umo}")
                    continue

                target = Target(platform_name, target_id, target_type)
                await platform.send_message(target, chain)
                self.logger.info(f"已向 {umo} 发送每日物种介绍")
            except Exception as e:
                self.logger.error(f"向 {umo} 发送消息失败: {e}")