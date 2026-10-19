# config.py 自定义配置,包括阅读次数、推送token的填写
import os
import re

"""
可修改区域
默认使用本地值如果不存在从环境变量中获取值
"""

# 阅读次数 默认40次/20分钟
READ_NUM = int(os.getenv('READ_NUM') or 40)
# 需要推送时可选，可选pushplus、wxpusher、telegram
PUSH_METHOD = "" or os.getenv('PUSH_METHOD')
# pushplus推送时需填
PUSHPLUS_TOKEN = "" or os.getenv("PUSHPLUS_TOKEN")
# telegram推送时需填
TELEGRAM_BOT_TOKEN = "" or os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = "" or os.getenv("TELEGRAM_CHAT_ID")
# wxpusher推送时需填
WXPUSHER_SPT = "" or os.getenv("WXPUSHER_SPT")
# SeverChan推送时需填
SERVERCHAN_SPT = "" or os.getenv("SERVERCHAN_SPT")


# read接口的bash命令，本地部署时可对应替换headers、cookies
curl_str = os.getenv('WXREAD_CURL_BASH')

# headers、cookies是一个省略模版，本地或者docker部署时对应替换
cookies = {
    'RK': 'oxEY1bTnXf',
    'ptcz': '53e3b35a9486dd63c4d06430b05aa169402117fc407dc5cc9329b41e59f62e2b',
    'pac_uid': '0_e63870bcecc18',
    'iip': '0',
    '_qimei_uuid42': '183070d3135100ee797b08bc922054dc3062834291',
    'wr_avatar': 'https%3A%2F%2Fthirdwx.qlogo.cn%2Fmmopen%2Fvi_32%2FeEOpSbFh2Mb1bUxMW9Y3FRPfXwWvOLaNlsjWIkcKeeNg6vlVS5kOVuhNKGQ1M8zaggLqMPmpE5qIUdqEXlQgYg%2F132',
    'wr_gender': '0',
}

headers = {
    'accept': 'application/json, text/plain, */*',
    'accept-language': 'zh-CN,zh;q=0.9,en;q=0.8,en-GB;q=0.7,en-US;q=0.6,ko;q=0.5',
    'baggage': 'sentry-environment=production,sentry-release=dev-1730698697208,sentry-public_key=ed67ed71f7804a038e898ba54bd66e44,sentry-trace_id=1ff5a0725f8841088b42f97109c45862',
    'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36 Edg/131.0.0.0',
}


# 书籍（木心全集·典藏套装十六册）
book = [
    "35032fe071f6e47f3506809"
]

# 章节
chapter = [
    "c9f326703452c9f95a0a069",
    "e5832f703453e58cc5ca402"
]

"""
建议保留区域|默认读木心全集，其它书籍自行测试时间是否增加
"""
data = {
    "appId": "wb182564874663h1864807034",
    "b": "35032fe071f6e47f3506809",
    "c": "c9f326703452c9f95a0a069",
    "ci": 396,
    "co": 393,
    "sm": "如响[1]\n偕偕仲子\n朝夕溶漾[2]\n栖迟偃仰[3]\n斐亹成",
    "pr": 100,
    "ts": 1792436558000,
    "rn": 466,
    "sg": "2b2ec618394b99deea35104168b86381da9f8946d4bc234e062fa320155409fb",
    "ct": 1792436558,
    "ps": "23532fb07aaf0a87g016336",
    "pc": "23532fb07aaf0a87g016336",
    "s": "36cc0815"
}

# 阅读位置池：每组都来自一次真实翻页请求的 (c, ci, co, sm, pr)
# main.py 每次随机取一组，ci/co/sm/pr 与 c 严格对应，效果等同真实翻页
positions = [
    {"c": "e5832f703453e58cc5ca402", "ci": 397, "co": 393, "pr": 100, "sm": "雾豹雾豹其藏泽丽文章[1]谁从公木剑履趪"},
    {"c": "e5832f703453e58cc5ca402", "ci": 397, "co": 1855, "pr": 33, "sm": "[2]趪趪（huāng）​，武猛貌。张衡"},
    {"c": "b9d322b03454b9d487a3041", "ci": 398, "co": 393, "pr": 33, "sm": "多朅[1]申江洋洋吴流活活[2]鱿鲔发发"},
    {"c": "b9d322b03454b9d487a3041", "ci": 398, "co": 1641, "pr": 33, "sm": "[3]鲔（wěi）​，鲟鱼。发发（bō）"},
    {"c": "8f13248034558f1d4362195", "ci": 399, "co": 393, "pr": 33, "sm": "如英[1]彼淇之子美如英美无度[2]猗嗟"},
    {"c": "8f13248034558f1d4362195", "ci": 399, "co": 1563, "pr": 33, "sm": "[3]猗嗟，叹美之辞。昌，美盛。[4]清"},
    {"c": "2cb32d1034562cbca4487a6", "ci": 400, "co": 928, "pr": 33, "sm": "其乐只且之子傞傞佽之卸[5]左右而中挹去"},
    {"c": "d6e329c0345ad6ef5f7f1a0", "ci": 404, "co": 393, "pr": 34, "sm": "常棣[1]常棣之华鄂不韡韡凡今之人莫如良"},
    {"c": "dd7321f0345cdd77279fe9a", "ci": 406, "co": 393, "pr": 100, "sm": "斯恩[1]彼风发兮彼机偈兮顾瞻云路中心怛"},
]


def convert(curl_command):
    """提取bash接口中的headers与cookies
    支持 -H 'Cookie: xxx' 和 -b 'xxx' 两种方式的cookie提取
    """
    # 提取 headers
    headers_temp = {}
    for match in re.findall(r"-H '([^:]+): ([^']+)'", curl_command):
        headers_temp[match[0]] = match[1]

    # 提取 cookies
    cookies = {}
    
    # 从 -H 'Cookie: xxx' 提取
    cookie_header = next((v for k, v in headers_temp.items() 
                         if k.lower() == 'cookie'), '')
    
    # 从 -b 'xxx' 提取
    cookie_b = re.search(r"-b '([^']+)'", curl_command)
    cookie_string = cookie_b.group(1) if cookie_b else cookie_header
    
    # 解析 cookie 字符串
    if cookie_string:
        for cookie in cookie_string.split('; '):
            if '=' in cookie:
                key, value = cookie.split('=', 1)
                cookies[key.strip()] = value.strip()
    
    # 移除 headers 中的 Cookie/cookie
    headers = {k: v for k, v in headers_temp.items() 
              if k.lower() != 'cookie'}

    return headers, cookies


headers, cookies = convert(curl_str) if curl_str else (headers, cookies)
