from astrbot.api.event import filter, AstrMessageEvent
from astrbot.api.star import Context, Star, register
from astrbot.api import logger
from astrbot.api.message_components import Plain
import aiohttp
import asyncio
from typing import Optional, Dict, Any


@register("IP地理位置查询", "cloudcranesss", "优化版IP归属地查询插件，支持真实客户端IP获取", "1.2.0",
          "https://github.com/cloudcranesss/astrbot_plugin_ip_location")
class IPLookupPlugin(Star):
    """IP归属地查询插件"""
    
    def __init__(self, context: Context):
        super().__init__(context)
        
        # IP查询API
        self.api_urls = [
            "https://api.52vmy.cn/api/query/itad/pro",
            "https://api.vvhan.com/api/ipInfo"
        ]
        
        # 超时配置
        self.timeout = aiohttp.ClientTimeout(total=10, connect=5)
        
        # 创建会话
        connector = aiohttp.TCPConnector(
            limit=10,
            limit_per_host=5,
            ttl_dns_cache=300
        )
        
        self.session = aiohttp.ClientSession(
            connector=connector,
            timeout=self.timeout,
            headers={
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
            }
        )
        
        logger.info("🌐 IP查询插件已初始化")

    async def terminate(self):
        """优雅关闭会话"""
        if self.session and not self.session.closed:
            await self.session.close()
            logger.info("IP查询会话已关闭")

    async def _query_ip_info(self, ip: str) -> Optional[Dict[str, Any]]:
        """查询IP信息"""
        try:
            # 52vmy.cn API
            url = f"https://api.52vmy.cn/api/query/itad/pro?ip={ip}"
            async with self.session.get(url) as response:
                if response.status == 200:
                    result = await response.json()
                    if result.get("code") == 200:
                        data = result.get("data", {})
                        return {
                            "ip": ip,
                            "country": data.get("country", "未知"),
                            "region": data.get("province", "未知"),
                            "city": data.get("city", "未知"),
                            "isp": data.get("isp", "未知"),
                            "lat": float(data.get("latitude", 0)),
                            "lon": float(data.get("longitude", 0)),
                            "timezone": "未知"
                        }

            # vvhan.com API
            url = f"https://api.vvhan.com/api/ipInfo?ip={ip}"
            async with self.session.get(url) as response:
                if response.status == 200:
                    data = await response.json()
                    if data.get("success"):
                        info = data.get("info", {})
                        return {
                            "ip": data.get("ip", ip),
                            "country": info.get("country", "未知"),
                            "region": info.get("prov", "未知"),
                            "city": info.get("city", "未知"),
                            "isp": info.get("isp", "未知"),
                            "lat": 0,
                            "lon": 0,
                            "timezone": "未知"
                        }
                        
        except asyncio.TimeoutError:
            logger.error(f"查询IP {ip} 超时")
        except aiohttp.ClientError as e:
            logger.error(f"网络错误查询IP {ip}: {e}")
        except Exception as e:
            logger.error(f"查询IP信息失败 {ip}: {type(e).__name__}: {e}")
        
        return None



    @filter.command_group("ip")
    async def ip_group(self, event: AstrMessageEvent):
        """IP查询命令组"""
        if not event.message_str.strip():
            yield event.plain_result(
                "🌐 IP查询插件命令:\n"
                "  ip 查询 [IP地址] - 查询指定IP的归属地\n"
                "  ip 状态 - 查看插件状态"
            )

    @ip_group.command("查询")
    async def query_ip(self, event: AstrMessageEvent):
        """查询指定IP的归属地"""
        try:
            # 获取IP地址
            parts = event.message_str.strip().split()
            if len(parts) < 3:
                yield event.plain_result("❌ 请提供IP地址，格式：ip 查询 8.8.8.8")
                return
            
            ip = parts[2]
            
            # 验证IP格式（简化验证）
            if not self._is_valid_ip(ip):
                yield event.plain_result("❌ 请输入有效的IP地址")
                return
            
            yield event.plain_result(f"🔍 正在查询IP {ip} 的信息...")
            
            info = await self._query_ip_info(ip)
            
            if info:
                result = (
                    f"📍 IP地址：{info['ip']}\n"
                    f"🏳️ 国家：{info['country']}\n"
                    f"🗺️ 地区：{info['region']}\n"
                    f"🏙️ 城市：{info['city']}\n"
                    f"🏢 ISP：{info['isp']}\n"
                    f"📍 坐标：{info['lat']}, {info['lon']}\n"
                    f"🕐 时区：{info['timezone']}"
                )
                yield event.plain_result(result)
            else:
                yield event.plain_result("❌ 查询失败，请稍后重试")
                
        except Exception as e:
            logger.error(f"查询IP异常: {e}")
            yield event.plain_result("❌ 查询时出现错误")



    @ip_group.command("状态")
    async def check_plugin_status(self, event: AstrMessageEvent):
        """检查插件状态"""
        status = (
            "📊 IP查询插件状态:\n"
            f"API数量: {len(self.api_urls)}\n"
            f"会话状态: {'活跃' if not self.session.closed else '已关闭'}\n"
            f"超时设置: {self.timeout.total}秒\n"
            f"支持命令: ip 查询, ip 我的, ip 状态"
        )
        yield event.plain_result(status)

    def _is_valid_ip(self, ip: str) -> bool:
        """验证IP地址格式"""
        import re
        pattern = r'^(?:(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\.){3}(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)$'
        return bool(re.match(pattern, ip))