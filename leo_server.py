# leo_server.py
import requests
from fastmcp import FastMCP

mcp = FastMCP("WeatherService")

# 你的心知天气 API 密钥
API_SECRET = ''

@mcp.tool()
def get_weather(city: str):
    """
    获取对应城市当前的实时天气
    :param city: 城市名称，如 "北京", "shanghai"
    :return: 城市当前天气的描述
    """
    url = f'https://api.seniverse.com/v3/weather/now.json?key={API_SECRET}&location={city}&language=zh-Hans&unit=c'
    try:
        response = requests.get(url)
        data = response.json()
        if 'results' in data:
            weather = data['results'][0]['now']
            return f"{city}当前天气：{weather['text']}，气温 {weather['temperature']}°C。"
        else:
            return f"无法获取 {city} 的实时天气信息，请检查城市名称是否正确。"
    except Exception as e:
        return f"查询当前天气时出现错误: {e}"

@mcp.tool()
def get_forecast(city: str, days: int = 3):
    """
    获取对应城市未来几天的天气预报（最高支持3天）
    :param city: 城市名称
    :param days: 预测天数（默认3天）
    :return: 城市天气预报的描述
    """
    # 免费版心知天气 daily.json 最多支持3天
    url = f'https://api.seniverse.com/v3/weather/daily.json?key={API_SECRET}&location={city}&language=zh-Hans&unit=c&start=0&days={days}'
    try:
        response = requests.get(url)
        data = response.json()
        if 'results' in data:
            forecasts = data['results'][0]['daily']
            result_str = f"{city}未来{len(forecasts)}天天气预报：\n"
            for day in forecasts:
                result_str += f"- {day['date']}: 白天{day['text_day']}，夜间{day['text_night']}，气温 {day['low']}°C ~ {day['high']}°C\n"
            return result_str
        else:
            return f"无法获取 {city} 的天气预报信息。"
    except Exception as e:
        return f"查询天气预报时出现错误: {e}"

if __name__ == '__main__':
    mcp.run()