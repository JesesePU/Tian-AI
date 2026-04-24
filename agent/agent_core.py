#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
miniGPT Agent 核心 — 自主规划 + 工具执行 + 结果分析

工作流：
  用户输入
    → 分析意图（问答还是命令/任务？）
    → 如果是命令/任务：
      1. 解析任务目标
      2. 规划执行步骤（分步分解）
      3. 逐步调用工具执行
      4. 收集结果
      5. 生成最终回答（含执行结果）
    → 如果是普通问答 → 交给 consciousness 处理
"""

import sys
import os
import re
import json
import random
import time
import traceback
import shlex
import textwrap

# 导入新架构模块（替代旧版 consciousness）
# 路径处理
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import tools

# ─── 命令/任务识别模式 ─────────────────────
# 这些模式表明用户想要执行操作，而不是简单问答
COMMAND_PATTERNS = [
    # 执行命令
    r'(?:帮我)?(?:执行|运行|跑一下|运行一下)(?:命令|脚本|程序|代码)',
    r'(?:帮我)?(?:执行|运行|跑一下)\s*(?:shell|bash|python|命令)',
    r'(?:执行|运行|跑).*?(?:命令|指令)',
    r'^[a-z]+\s+[-]+',  # 命令行参数模式（如 python install.py --help）
    r'(?:帮我)?(?:创建|新建|生成|写|编写|编辑|修改|删除|重命名|移动|复制|拷贝|压缩|解压|安装|卸载|下载|上传|搜索|查找|查看|打开)\s',
    # 文件操作
    r'(?:创建|新建|生成|写|编写|编辑|修改|删除|重命名|移动|复制|拷贝).*?(?:文件|文件夹|目录|脚本)',
    r'(?:压缩|解压|打包|解包).*?(?:文件|文件夹)',
    # 系统操作
    r'(?:安装|卸载|下载|update|upgrade|install|remove|apt|pip)\s',
    r'(?:查看|检查|显示|列出|统计|查询).*?(?:目录|文件|进程|内存|磁盘|网络|IP|端口)',
    r'(?:查看|读取|打开).*?\.[a-z]+$',  # 查看xxx.py 文件读取命令
    r'(?:重启|启动|停止|停止|kill|杀掉|关闭).*?(?:服务|进程|程序)',
    # 代码操作
    r'(?:帮我)?(?:写|编写|实现|写个|写一个).*?(?:代码|脚本|函数|类|模块|程序)',
    r'(?:帮我)?(?:重构|优化|修复|修改|改进|升级).*?(?:代码|脚本|函数|类)',
    # 数据操作
    r'(?:查询|搜索|查找|统计|分析|解析|处理|转换|导出|导入).*?(?:数据|文件|日志|文本|CSV|JSON|XML)',
    # 调试
    r'(?:帮我)?(?:调试|测试|检查|诊断|排查).*?(?:问题|bug|错误|异常|报错)',
    # 环境信息
    r'查看.*?(?:环境|配置|设置|信息|版本)',
    r'(?:当前|现在).*?(?:目录|路径|位置|时间|日期|几点|什么时候)',
    r'(?:现在|当前)(?:时间|日期|几点|什么时候)',
    r'(?:谁|什么用户)',
    # 系统信息（纯问句但应该走系统命令）
    r'现在几点', r'现在几点了', r'几点了',
    # 网络
    r'(?:ping|curl|wget|nc|telnet|ssh|scp|rsync).*',
    # git
    r'(?:git|clone|commit|push|pull|branch|merge|rebase|stash).*',
    # 明确的任务描述
    r'(?:我需要你|帮我|请你|麻烦你|你帮我).*(?:做|写|执行|运行|创建|修改|删除|查找|搜索|安装|配置|设置|启动|停止)',
]

# 纯问答模式（不应该触发命令执行）
QUESTION_PATTERNS = [
    r'什么是.{2,}', r'是什么', r'是什么意思', r'什么叫做',
    r'解释', r'说明', r'介绍',
    r'为什么', r'如何.{2,}', r'怎么.{2,}',
    r'和.*的区别', r'与.*的对比',
    r'你是谁', r'你能做什么', r'你有什么功能',
    r'你好', r'hi\\b', r'hello\\b',
]


def is_command_request(text):
    """判断用户输入是否是一个命令/任务请求"""
    text = text.strip()

    # 短文本优先检查常见命令
    if len(text) <= 10:
        # cd/ls/pwd 等
        cmd_short = re.match(r'^(cd|ls|pwd|whoami|id|date|uptime|uname|df|du|free|ps|top|netstat|ip|ping)\s*', text)
        if cmd_short:
            return True

    # 先排除纯问答
    for p in QUESTION_PATTERNS:
        if re.search(p, text):
            return False

    # 检查命令模式
    for p in COMMAND_PATTERNS:
        if re.search(p, text):
            return True

    # 检查是否包含命令行语法（如管道、重定向）
    if re.search(r'[|><&;]', text) and len(text) >= 5:
        return True

    # 以命令动词开头
    cmd_verbs = ['cd ', 'ls ', 'cat ', 'echo ', 'mkdir ', 'rm ', 'cp ', 'mv ', 'touch ',
                 'chmod ', 'chown ', 'grep ', 'find ', 'sort ', 'wc ', 'head ', 'tail ',
                 'pip ', 'npm ', 'node ', 'python', 'git ', 'make ', 'cmake ',
                 'curl ', 'wget ', 'tar ', 'zip ', 'unzip ', 'gzip ',
                 'apt ', 'pkg ', 'termux-', 'ssh ', 'scp ',
                 'kill ', 'pkill ', 'nohup ', 'docker ', 'ffmpeg ',
                 'sudo ', 'su ']
    for v in cmd_verbs:
        if text.startswith(v):
            return True

    return False


class Agent:
    """Tian AI Agent — 自主执行 agent（适配新 Thinker-Talker 架构）"""

    def __init__(self, identity=None, emotion_state=None, thinker=None, talker=None, **kwargs):
        self.identity = identity  # TianIdentity 实例
        self.emotion_state = emotion_state  # EmotionalState 实例
        self.thinker = thinker  # ThinkerRouter 实例
        self.talker = talker  # TalkerRouter 实例
        
        # 兼容旧接口（consciousness参数仍然可用）
        if 'consciousness' in kwargs:
            self.consciousness = kwargs['consciousness']
        self.tools = tools
        self.conversation_history = []  # 对话历史
        self.execution_history = []     # 执行历史

    def process(self, user_input, consciousness_result=None):
        """
        处理用户输入：
        - 如果是命令/任务 → 用 Agent 执行工具
        - 如果是普通问答 → 返回原 consciousness 结果
        """
        if is_command_request(user_input):
            return self._handle_command(user_input, consciousness_result)

        # 普通问答 — 直接使用新架构 Thinker-Talker 管线
        if self.thinker and self.talker:
            talker_result = self.talker.route(user_input, thinker=self.thinker,
                                               emotion_state=self.emotion_state)
            return {
                'mode': 'chat',
                'answer': talker_result['response'],
                'metadata': talker_result,
            }
        elif consciousness_result:
            return {
                'mode': 'chat',
                'answer': consciousness_result['answer'],
                'metadata': consciousness_result,
            }
        
        return {
            'mode': 'chat',
            'answer': None,
            'metadata': {},
        }

    def _handle_command(self, user_input, consciousness_result=None):
        """处理命令/任务请求"""
        start_time = time.time()

        # Step 1: 解析意图
        parsed = self._parse_intent(user_input)

        # Step 2: 规划执行步骤
        plan = self._make_plan(parsed, user_input)

        # Step 3: 逐步执行
        execution_log = []
        tool_outputs = []
        for step in plan:
            step_start = time.time()
            result = self._execute_step(step)
            elapsed = time.time() - step_start
            step['duration'] = round(elapsed, 2)
            step['result'] = result
            step['status'] = 'success' if result.get('success') else 'error'
            execution_log.append(step)
            tool_outputs.append({
                'step': step['description'],
                'tool': step.get('tool', ''),
                'success': result.get('success', False),
                'output': result.get('result', result.get('error', '')),
            })

        # Step 4: 生成回复
        total_time = time.time() - start_time
        answer = self._compose_response(user_input, tool_outputs, execution_log, total_time)

        self.execution_history.append({
            'input': user_input,
            'plan': plan,
            'outputs': tool_outputs,
            'duration': round(total_time, 2),
        })

        # 回填到对话历史（让后续对话知道Agent刚才做了什么）
        if self.identity:
            self.identity.on_interaction(f"[agent_cmd] {user_input[:50]}", 
                                          str(answer)[:200] if not isinstance(answer, dict) else str(answer.get('answer', ''))[:200])
        elif hasattr(self, 'consciousness') and self.consciousness:
            self.consciousness.short_term.append({
                'time': start_time,
                'user_input': user_input,
                'concepts': [],
                'attention_focus': parsed.get('target') or parsed.get('action_type', ''),
                'answer': answer if isinstance(answer, str) else answer.get('answer', str(answer)),
                'kb_hits': 0,
                'semantic_intent': 'agent_cmd',
                'agent_mode': True,
            })

        return {
            'mode': 'agent',
            'answer': answer,
            'plan': [{'tool': s.get('tool', ''), 'description': s['description'],
                       'status': s.get('status', '')} for s in plan],
            'execution_log': execution_log,
            'duration': round(total_time, 2),
        }

    # 自然语言 → 实际命令映射
    _NL_COMMAND_MAP = [
        # 磁盘存储
        (r'(?:磁盘|存储|硬盘|空间|容量|大小).*(?:使用|占用|剩余|情况|多少|状态)', 'df -h'),
        (r'(?:剩余|可用|空闲).*(?:空间|存储|容量|磁盘|位置)', 'df -h'),
        (r'(?:查看|检查|显示).*(?:磁盘|空间|存储|容量)', 'df -h'),
        # 内存
        (r'(?:内存|RAM|运行内存).*(?:使用|占用|剩余|情况|多少|状态)', 'free -h'),
        (r'查看.*(?:内存|ram)', 'free -h'),
        # 目录列表
        (r'(?:查看|显示|列出|列出).*(?:目录|文件夹|文件)(?:列表|内容|结构)?\s*(.*?)(?:\s*$|的|呢)', 'ls -la '),
        (r'(?:当前|现)?(?:目录|位置|路径|文件夹)\s*(?:内容|文件|有什么|有哪些)', 'ls -la'),
        (r'(?:查看|看看)(?:当前)?目录', 'ls -la'),
        # 进程
        (r'(?:进程|程序|服务).*(?:列表|查看|显示|有哪些|在运行)', 'ps aux --sort=-%mem | head -20'),
        (r'(?:查看|显示).*(?:进程|运行)', 'ps aux | head -20'),
        # 网络
        (r'(?:查看|检查|显示).*(?:网络|IP|地址|端口|连接)', "netstat -tlnp 2>/dev/null || ss -tlnp"),
        (r'(?:IP|ip).*?(?:地址|多少)', "hostname -I 2>/dev/null || ifconfig 2>/dev/null | head -5"),
        # 系统信息
        (r'(?:系统|设备|手机|平板).*(?:信息|型号|版本|详情)', 'uname -a'),
        (r'(?:查看|检查).*(?:版本|信息|环境)', 'uname -a && echo "---" && df -h / && echo "---" && free -h'),
        (r'现在.*(?:时间|日期|几点)', 'date'),
        (r'(?:当前|现在|今天).*(?:时间|日期)', 'date'),
        (r'(?:谁|什么用户|用户)', 'whoami && echo "---" && id'),
        # 别名
        (r'^cd\s', 'cd '),  # cd 命令
        (r'^ls\s', 'ls '),
        (r'^pwd\s*$', 'pwd'),
        (r'^date\s*$', 'date'),
        (r'^whoami\s*$', 'whoami'),
        (r'^df\s', 'df '),
    ]

    def _parse_intent(self, text):
        """解析用户意图 — v2 自然语言 → 实际命令映射"""
        parsed = {
            'original': text,
            'action_type': None,
            'target': None,
            'params': {},
        }

        # 2. 文件读取（优先于自然语言命令映射，防被目录列表模式误匹配）
        file_read = re.search(r'(?:读取|查看|打开|显示|看[一下]?|读)\s*(?:文件)?\s*([a-zA-Z0-9_\-]+\.[a-z]+(?:\.[a-z]+)?)(?:\s*$|的内容|，|。|文件|的前面|的后面|的第)', text)
        if file_read:
            path = file_read.group(1).strip()
            parsed['action_type'] = 'read_file'
            parsed['target'] = path
            parsed['params']['path'] = path
            return parsed

        # 3. 文件创建/写入（需要生成内容的智能操作）
        write_patterns = [
            # 优先：反引号/引号包住的文件名
            r'(?:帮我)?(?:写|创建|新建|生成|编写|写个|写一个)\s*(?:一个\s*)?(?:Python|shell|bash|脚本|程序|代码|文件)\s*(?:叫|名为)?\s*[`\'"](.+?\.[a-z]+)[`\'"]',
            # 优先级高：写什么什么.xxx → 提取文件名
            r'(?:帮我)?(?:写|创建|新建|生成|编写|写个|写一个)\s*(?:一个\s*)?(?:Python|shell|bash|脚本|程序|代码|文件)\s*(?:叫|名为|\s+叫\s+)?\s*(.+?\.[a-z]+)(?:\s*$|，|。|用|来|做|实现)',
            # 通用：包含明确的文件后缀
            r'(?:帮我)?(?:写|创建|新建|生成|编写|写个|写一个)\s*(?:一个\s*)?(?:Python|shell|bash|脚本|程序|代码|文件)\s*(?:叫|名为|\s+叫\s+)?\s*(.+?)(?:\s*$|，|。|来|做|实现|用于)',
            r'(?:帮我)?(?:写|创建|新建|生成|编写)\s*(?:文件|脚本)\s*(?:叫|名为)?\s*(.+?\.[a-z]+)(?:\s*$|，|。)',
            r'(?:帮我)?写\s*(?:个|一个)\s*(.+?)(?:脚本|程序|文件)',
        ]
        for p in write_patterns:
            m = re.search(p, text)
            if m:
                parsed['action_type'] = 'write_code'
                raw_target = m.group(1).strip() if m.lastindex and m.group(1) else 'script.py'
                # 从 raw_target 中提取真正的文件名（舍弃前缀）
                # 例如 "脚本叫fib.py" → "fib.py", "一个Python脚本" → "script.py"
                name_match = re.search(r'([a-zA-Z0-9_\-]+\.[a-z]+(?:\.[a-z]+)?)', raw_target)
                if name_match:
                    parsed['target'] = name_match.group(1)
                else:
                    parsed['target'] = raw_target if '.' in raw_target else f'{raw_target}.py'
                parsed['params']['description'] = text
                return parsed

        # 2. 自然语言 → shell 命令映射（优先使用长匹配）
        input_lower = text.lower()
        # 按匹配长度降序排序，避免短模式提前匹配
        sorted_map = sorted(self._NL_COMMAND_MAP, key=lambda x: len(x[0]), reverse=True)
        for pattern, command in sorted_map:
            if re.search(pattern, input_lower):
                # 如果是 `ls -la ` 这类带后缀的，尝试提取路径
                if command.endswith(' '):
                    # 从文本提取目标路径（排除匹配本身）
                    # 先移除匹配到的模式部分，取剩下的内容
                    match_obj = re.search(pattern, input_lower)
                    matched_text = match_obj.group(0) if match_obj else ''
                    remaining = text.lower().replace(matched_text, '', 1).strip()
                    # 清理无意义后缀
                    remaining = re.sub(r'^(目录|文件夹|文件)\s*', '', remaining)
                    remaining = re.sub(r'\s*(呢|吧|啊|呀|给我|告诉我|一下)\s*$', '', remaining)
                    if remaining and len(remaining) < 100 and re.match(r'^[/\.\w\-\s]+$', remaining):
                        command = command.strip() + ' ' + remaining
                    else:
                        command = command.strip()
                parsed['action_type'] = 'shell'
                parsed['params']['command'] = command
                return parsed

        # 4. 搜索文件
        search_patterns = [
            r'(?:搜索|查找|找|寻找)\s*(?:文件|内容|关键字)?\s*[`"\'\(（](.+?)[`"\'\)）]',
            r'(?:搜索|查找|找|寻找)\s*(?:文件|内容|关键字)?\s*[:：](.+?)(?:\s*$|，|。|中|里|在)',
            r'(?:搜索|查找|找|寻找)\s*(?:包含|含有|包括|匹配).*?(.+?)(?:\s*$|的文件|的内容|，|。|中|里)',
            r'(?:搜索|查找|找|寻找)\s*(?:文件|内容).*?(?:(?:包含|含有|包括|匹配|里有没有)\s*)(.+?)(?:\s*$|，|。|中|里|在)',
            r'(?:搜索|查找|找|寻找)\s*(.+?)(?:\s*文件|\s*内容|\s*关键字|\s*关键词)',
            r'搜索.*?(?:包含|含有|包括)\s*(.+?)(?:\s*$|的文件|的内容|，|。|中|在)',
        ]
        for p in search_patterns:
            m = re.search(p, text)
            if m:
                parsed['action_type'] = 'search_files'
                parsed['params']['pattern'] = m.group(1).strip()
                return parsed

        # 5. 反引号命令（`command`）
        backtick = re.findall(r'`([^`]+)`', text)
        if backtick:
            parsed['action_type'] = 'shell'
            parsed['params']['command'] = backtick[0]
            return parsed

        # 6. 纯 shell 命令检测（以命令动词开头）
        cmd_verbs = ['cd ', 'ls ', 'cat ', 'echo ', 'mkdir ', 'rm ', 'cp ', 'mv ', 'touch ',
                     'chmod ', 'grep ', 'find ', 'sort ', 'wc ', 'head ', 'tail ',
                     'pip ', 'npm ', 'node ', 'python', 'git ', 'make ',
                     'curl ', 'wget ', 'tar ', 'zip ', 'unzip ',
                     'apt ', 'pkg ', 'ssh ', 'scp ', 'kill ', 'pkill ', 'sudo ',
                     'ps ', 'df ', 'free ', 'du ', 'date ', 'whoami', 'id ', 'uname ',
                     'netstat', 'ip ', 'ifconfig', 'hostname']
        stripped = text.strip()
        for v in cmd_verbs:
            if stripped.startswith(v):
                parsed['action_type'] = 'shell'
                parsed['params']['command'] = stripped
                return parsed

        # 7. 兜底：清理"帮我/请/麻烦你/你帮我"前缀后当 shell 命令
        cleaned = stripped
        for prefix in ['帮我', '请', '麻烦你', '你帮我']:
            if cleaned.startswith(prefix):
                cleaned = cleaned[len(prefix):].strip()
        if cleaned and cleaned != stripped:
            # 但清理后如果是纯问句，交给知识库
            if re.match(r'^(什么|怎么|如何|为什么|哪些|有没有|是不是|能不能|会不会|几|哪|多少|有否|是否)', cleaned):
                parsed['action_type'] = 'knowledge_query'
                parsed['params']['concept'] = text
                return parsed
            parsed['action_type'] = 'shell'
            parsed['params']['command'] = cleaned
            return parsed

        # 8. 最终兜底：知识库查询
        parsed['action_type'] = 'knowledge_query'
        parsed['params']['concept'] = text
        return parsed

    def _make_plan(self, parsed, user_input):
        """生成执行计划 — v2 支持自然语言映射"""
        plan = []
        action = parsed['action_type']

        if action == 'write_code':
            # 写代码/脚本 — 用 shell 生成包含实际内容的脚本
            desc = parsed['params'].get('description', user_input)
            target_name = parsed.get('target', 'script.py')
            # 如果是 Python 脚本，生成骨架
            if target_name.endswith('.py'):
                code = f'''#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# Generated by miniGPT Agent
# Request: {desc[:60]}

def main():
    """
    TODO: 实现功能
    """
    pass

if __name__ == '__main__':
    main()
'''
            elif target_name.endswith('.sh'):
                code = f'''#!/data/data/com.termux/files/usr/bin/bash
# Generated by miniGPT Agent
# Request: {desc[:60]}

echo "脚本已生成"
'''
            else:
                code = f'# Generated by miniGPT Agent\n# {desc[:60]}\n'
            plan.append({
                'tool': 'shell',
                'description': f'生成脚本: {target_name}',
                'params': {'command': f'cat > {target_name} << \'HERMESEOF\'\n{code}\nHERMESEOF\nchmod +x {target_name}', 'timeout': 10},
            })
            plan.append({
                'tool': 'shell',
                'description': f'查看 {target_name}',
                'params': {'command': f'ls -la {target_name} && echo "---" && head -5 {target_name}', 'timeout': 5},
            })
        elif action == 'read_file':
            plan.append({
                'tool': 'read_file',
                'description': f'读取文件 {parsed["target"]}',
                'params': parsed['params'],
            })
        elif action == 'search_files':
            plan.append({
                'tool': 'search_files',
                'description': f'搜索: {parsed["params"]["pattern"]}',
                'params': {'pattern': parsed['params']['pattern'], 'path': '.', 'target': 'content'},
            })
        elif action == 'shell':
            cmd = parsed['params']['command']
            plan.append({
                'tool': 'shell',
                'description': f'{cmd[:80]}',
                'params': {'command': cmd, 'timeout': 60},
            })
        elif action == 'knowledge_query':
            plan.append({
                'tool': 'knowledge_query',
                'description': f'查询知识库: {parsed["params"]["concept"][:30]}',
                'params': {'concept': parsed['params']['concept']},
            })
        else:
            plan.append({
                'tool': 'shell',
                'description': f'{user_input[:80]}',
                'params': {'command': user_input, 'timeout': 60},
            })

        return plan

    def _execute_step(self, step):
        """执行单个步骤"""
        tool_name = step['tool']
        params = step['params']
        result = tools.call_tool(tool_name, **params)
        return result

    def _compose_response(self, user_input, tool_outputs, execution_log, total_time):
        """生成最终回复"""
        # 检查整体成功/失败
        all_ok = all(o['success'] for o in tool_outputs)
        total_steps = len(tool_outputs)

        if all_ok:
            # 检查是否有 knowledge_query 步骤（此时应该用 consciousness 原始回复）
            has_kq = any(o['tool'] == 'knowledge_query' for o in tool_outputs)
            
            if has_kq and len(tool_outputs) == 1:
                # 纯知识库查询
                if self.thinker and self.talker:
                    # 使用新 Thinker-Talker 管线
                    talker_result = self.talker.route(user_input, thinker=self.thinker, 
                                                       emotion_state=self.emotion_state)
                    state_summary = self.identity.get_state_summary() if self.identity else {}
                    answers = {
                        'answer': talker_result['response'],
                        'mode': 'chat',
                        'source': 'agent_thinker',
                        'mood': state_summary.get('mood', '平静'),
                        'confidence': 0.8,
                        'curiosity': state_summary.get('curiosity_level', 0.5),
                        'energy': state_summary.get('energy', 1.0),
                        'state_summary': state_summary,
                    }
                    return answers
                elif hasattr(self, 'consciousness') and self.consciousness:
                    # 回退到旧版 consciousness
                    kq_result = self.consciousness.process_input(user_input)
                    kq_state = self.consciousness.get_state_summary()
                    answers = {
                        'answer': kq_result['answer'],
                        'mode': 'chat' if 'mode' not in locals() else 'chat',
                        'source': 'local',
                        'mood': kq_result['mood'],
                        'motive': kq_result['motive'],
                        'confidence': kq_result['confidence'],
                        'curiosity': kq_result['curiosity'],
                        'energy': kq_result['energy'],
                        'focus': kq_result.get('attention'),
                        'inner_thought': kq_result.get('inner_thought', {}).get('content') if kq_result.get('inner_thought') else None,
                        'reflection': kq_result.get('reflection'),
                        'state_summary': {
                            'mood': kq_state['mood'],
                            'confidence': kq_state['confidence'],
                            'curiosity': kq_state['curiosity'],
                            'energy': kq_state['energy'],
                            'motive': kq_state['motive'],
                            'focus': kq_state['focus'],
                            'interactions': kq_state['interactions'],
                        }
                    }
                    # 已经通过 consciousness.process_input() 写入 short_term，无需重复
                    return answers  # 直接返回 consciousness 的格式

            # 收集输出
            outputs_parts = []
            for o in tool_outputs:
                out = o.get('output', '')
                if isinstance(out, dict):
                    # 针对不同工具做格式化
                    if 'items' in out:
                        items = out['items']
                        if items and isinstance(items[0], dict):
                            out_str = '\n'.join(f"{i['name']:30s} {i.get('size', 0):>8d}B  {i.get('type', '')}" for i in items[:20])
                        else:
                            out_str = '\n'.join(items[:20])
                        if len(items) > 20:
                            out_str += f'\n... 还有 {len(items)-20} 项'
                        outputs_parts.append(out_str)
                    elif 'stdout' in out:
                        stdout = out['stdout'].rstrip()
                        if stdout:
                            outputs_parts.append(stdout)
                        if out.get('exit_code') != 0:
                            outputs_parts.append(f'[退出码: {out["exit_code"]}]')
                    elif 'content' in out:
                        outputs_parts.append(out['content'][:2000])
                    elif 'results' in out:
                        for r in out['results']:
                            if isinstance(r, dict):
                                outputs_parts.append(r.get('content', str(r)))
                            else:
                                outputs_parts.append(str(r)[:200])
                    elif 'result' in out:
                        outputs_parts.append(str(out['result']))
                    elif 'matches' in out:
                        matches = out['matches']
                        if matches:
                            out_str = '\n'.join(m[:200] for m in matches[:30])
                            if len(matches) > 30:
                                out_str += f'\n... 还有 {len(matches)-30} 条结果'
                            outputs_parts.append(out_str)
                        else:
                            outputs_parts.append('(无匹配结果)')
                    elif 'results' in out:
                        # search_files 工具返回的结果列表
                        results = out['results']
                        if results:
                            for r in results[:30]:
                                if isinstance(r, str):
                                    outputs_parts.append(r[:200])
                                elif isinstance(r, dict):
                                    outputs_parts.append(r.get('content', str(r)[:200]))
                                else:
                                    outputs_parts.append(str(r)[:200])
                            if len(results) > 30:
                                outputs_parts.append(f'... 还有 {len(results)-30} 条结果')
                        else:
                            outputs_parts.append('(无匹配结果)')
                else:
                    outputs_parts.append(str(out)[:2000])

            output_text = '\n'.join(outputs_parts).strip()
        else:
            # 有错误
            errors = [o.get('error', '') for o in tool_outputs if not o['success']]
            output_text = f'执行出错: {"；".join(errors)}'

        # 构建回复
        if total_steps == 1:
            header = f'已执行（{total_time:.1f}秒）:\n'
        else:
            header = f'已执行 {total_steps} 步（{total_time:.1f}秒）:\n'
            for i, o in enumerate(tool_outputs):
                status_icon = '✅' if o['success'] else '❌'
                header += f'  {status_icon} {o["step"]}\n'

        result_text = header + '\n' + output_text[:4000] if output_text else header

        # 添加上下文感知的收尾
        if self.identity and total_steps > 0:
            state = self.identity.get_state_summary()
            mood = state.get('mood', '平静')
            if mood in ('困惑', '怀疑'):
                pass  # 命令执行相关时不需要表达困惑
            elif mood in ('兴奋', '自信') and all_ok:
                result_text += f'\n\n{random.choice(["一切顺利。还有什么需要？", "搞定！还需要我做什么吗？", "完成。"]):s}'
            elif not all_ok:
                result_text += f'\n\n{random.choice(["出了点问题，要不换个方式试试？", "这里出了点状况。", "没完全成功，你看看哪里不对？"]):s}'
            else:
                pass
        elif hasattr(self, 'consciousness') and self.consciousness and total_steps > 0:
            ctx = self.consciousness
            if ctx.mood in ('困惑', '怀疑'):
                pass  # 命令执行相关时不需要表达困惑
            elif ctx.mood in ('兴奋', '自信') and all_ok:
                result_text += f'\n\n{random.choice(["一切顺利。还有什么需要？", "搞定！还需要我做什么吗？", "完成。"]):s}'
            elif not all_ok:
                result_text += f'\n\n{random.choice(["出了点问题，要不换个方式试试？", "这里出了点状况。", "没完全成功，你看看哪里不对？"]):s}'
            else:
                pass

        return result_text
