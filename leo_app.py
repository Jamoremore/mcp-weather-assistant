# app.py
import json
import asyncio
import streamlit as st
from typing import List, Dict
import httpx
from openai import OpenAI
from fastmcp import Client

# --- 页面配置 ---
st.set_page_config(page_title="Leo 智能天气助手", page_icon="🌤️", layout="centered")
st.title("🌤️ Leo 智能天气助手")
st.caption("基于 Qwen 大模型 + MCP 协议 + 心知天气 API 构建")

# --- 初始化配置 ---
MODEL = "qwen-plus"
DASHSCOPE_API_KEY = ""

# 侧边栏设置
with st.sidebar:
    st.header("⚙️ 设置")
    st.markdown("- **模型**: `qwen-plus`\n- **工具集**: `FastMCP Server`")
    if st.button("清空对话历史"):
        st.session_state.messages = [
            {"role": "system",
             "content": "你是一个贴心、专业的AI天气助手。你需要根据用户的问题，判断是否需要调用天气查询工具，然后用通俗易懂、温暖的语气回答用户。"}
        ]
        st.rerun()

# 初始化 Session State 中的历史消息
if "messages" not in st.session_state:
    st.session_state.messages = [
        {
            "role": "system",
            "content": "你是一个贴心、专业的AI天气助手。你需要根据用户的问题，判断是否需要调用天气查询工具，然后用通俗易懂、温暖的语气回答用户。"
        }
    ]


# --- 核心交互逻辑 (Async) ---
async def process_chat(user_input: str, message_placeholder):
    """处理 MCP 连接、工具调用和 OpenAI 流式输出的核心函数"""

    no_proxy_client = httpx.Client(trust_env=False)
    openai_client = OpenAI(
        base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
        api_key=DASHSCOPE_API_KEY,
        http_client=no_proxy_client
    )

    # 启动 MCP 客户端连接到本地 Server
    async with Client("leo_server.py") as mcp_client:
        # 获取可用工具
        raw_tools = await mcp_client.list_tools()
        tools_list = [
            {
                "type": "function",
                "function": {
                    "name": tool.name,
                    "description": tool.description,
                    "parameters": tool.inputSchema
                }
            } for tool in raw_tools
        ]

        # 循环处理大模型的请求（处理可能连续多次的工具调用）
        while True:
            response = openai_client.chat.completions.create(
                model=MODEL,
                messages=st.session_state.messages,
                tools=tools_list,
                stream=True
            )

            full_content = ""
            tool_calls_dict = {}

            # 流式处理
            for chunk in response:
                if chunk.choices:
                    delta = chunk.choices[0].delta

                    # 处理文本流输出到 Streamlit
                    if delta.content:
                        full_content += delta.content
                        message_placeholder.markdown(full_content + "▌")  # 打字机效果光标

                    # 处理工具调用流
                    if delta.tool_calls:
                        for tc in delta.tool_calls:
                            idx = tc.index
                            if idx not in tool_calls_dict:
                                tool_calls_dict[idx] = {
                                    "id": tc.id or "", "type": "function",
                                    "function": {"name": tc.function.name or "",
                                                 "arguments": tc.function.arguments or ""}
                                }
                            else:
                                if tc.id: tool_calls_dict[idx]["id"] += tc.id
                                if tc.function.name: tool_calls_dict[idx]["function"]["name"] += tc.function.name
                                if tc.function.arguments: tool_calls_dict[idx]["function"][
                                    "arguments"] += tc.function.arguments

            # 最终文本渲染（去掉光标）
            if full_content:
                message_placeholder.markdown(full_content)

            tool_calls = [tool_calls_dict[k] for k in sorted(tool_calls_dict.keys())]

            # 1. 如果没有工具调用，对话回合结束
            if not tool_calls:
                st.session_state.messages.append({"role": "assistant", "content": full_content})
                break

            # 2. 如果有工具调用，执行工具
            st.session_state.messages.append({
                "role": "assistant", "content": full_content if full_content else None, "tool_calls": tool_calls
            })

            # 在前端显示状态框
            for tool_call in tool_calls:
                func_name = tool_call["function"]["name"]
                args_str = tool_call["function"]["arguments"]

                with st.status(f"🛠️ 正在调用本地工具: `{func_name}`...", expanded=True) as status:
                    st.write(f"**请求参数**: `{args_str}`")
                    try:
                        args = json.loads(args_str)
                        tool_response = await mcp_client.call_tool(func_name, args)
                        tool_result_text = tool_response.content[0].text
                        st.write(f"**返回结果**: {tool_result_text}")
                        status.update(label=f"✅ 工具 `{func_name}` 执行完毕", state="complete", expanded=False)
                    except Exception as e:
                        tool_result_text = f"错误: {e}"
                        status.update(label=f"❌ 工具 `{func_name}` 执行失败", state="error", expanded=False)

                    # 将工具结果追加到消息中，继续下一轮循环
                    st.session_state.messages.append({
                        'role': 'tool',
                        'tool_call_id': tool_call["id"],
                        'content': tool_result_text
                    })

            # 继续 while 循环，模型会基于 tool 的返回结果继续生成文本


# --- UI 渲染层 ---
# 渲染历史对话
for msg in st.session_state.messages:
    if msg["role"] == "user":
        with st.chat_message("user", avatar="👤"):
            st.markdown(msg["content"])
    elif msg["role"] == "assistant" and msg.get("content"):
        with st.chat_message("assistant", avatar="🤖"):
            st.markdown(msg["content"])

# 聊天输入框
if prompt := st.chat_input("你想查询哪里的天气？例如：北京今天热吗？周末适合去杭州玩吗？"):
    # 渲染用户输入
    with st.chat_message("user", avatar="👤"):
        st.markdown(prompt)
    st.session_state.messages.append({"role": "user", "content": prompt})

    # 渲染 AI 回复区域
    with st.chat_message("assistant", avatar="🤖"):
        message_placeholder = st.empty()
        # 运行异步逻辑
        asyncio.run(process_chat(prompt, message_placeholder))