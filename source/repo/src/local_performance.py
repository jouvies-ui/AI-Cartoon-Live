"""Local renderer capability contract and strict decoding of Qwen's performance plan."""
import json
import math

MAX_AUTO_REPLY_CHARS = 50


def limit_reply(text, limit=MAX_AUTO_REPLY_CHARS):
    """Final local guard; punctuation also counts, independent of model compliance."""
    if len(text) <= limit:
        return text
    prefix = text[:limit]
    # Prefer a complete sentence; otherwise stop at a clause without inventing
    # a new ending. No second LLM request delays a live reply.
    for endings in ('。！？!?；;', '，,、：:'):
        boundary = max((prefix.rfind(ch) for ch in endings), default=-1)
        if boundary >= 15:
            return prefix[:boundary + 1] if endings.startswith('。') else prefix[:boundary] + '。'
    return prefix[:limit - 1].rstrip('，,、：:；; ') + '…'


def limit_reply_segments(segments):
    text = ''.join(s['text'] for s in segments)
    short = limit_reply(text)
    if short == text:
        return segments
    out, offset = [], 0
    for segment in segments:
        piece = short[offset:offset + len(segment['text'])]
        if piece:
            out.append({**segment, 'text': piece})
        offset += len(segment['text'])
        if offset >= len(short):
            break
    return out

EXPRESSIONS = {'neutral', 'warm', 'concerned', 'still'}

ACTIONS = {'neutral': '恢复自然', 'smile': '微笑', 'surprise': '惊讶', 'blink': '眨眼',
           'frown': '皱眉', 'nod': '点头', 'shake': '摇头',
           'look_left': '向画面左侧看', 'look_right': '向画面右侧看'}
LIVE2D_ACTIONS = {**ACTIONS, 'selfie': '自拍'}
SYSTEM_PROMPT = '''你是完全本地运行的数字人助手。输入是 JSON，含 mode 和 text。
输出必须是一个 JSON 对象：{"speech":"自然中文回答","actions":["动作ID"],"expression":"neutral"}，不要代码块或其他文字。
speech总共不超过50字（含标点），只说最有用的一两句话。actions 最多四项，按执行顺序填写；没有明确需求时用 []。
可用动作只有：neutral 恢复自然、smile 微笑、surprise 抬眉睁眼表示惊讶、blink 眨眼、frown 皱眉、nod 点头、shake 摇头、look_left 向画面左看、look_right 向画面右看。
这些是短暂的表情或头部动作，会自动回到自然状态。没有手臂、走动、转身、拿物、换装、跳舞或任意生成行为能力；遇到这些请求应如实说明并给可用替代，禁止说已经做到。
用户要求做动作时，把要求转换为 actions；例如“先笑一下再点头”输出 ["smile","nod"]。
尊重否定、停止、引用、问题和假设：“不要笑”“解释微笑”“他说‘点头’是什么意思”都不触发相应动作；“停止动作”输出 ["neutral"]。
expression 是整句说话时的面部情绪：neutral 放松讲解，不固定露齿笑；warm 眉眼和脸颊一起温和微笑，用于祝贺、开心与亲切欢迎；concerned 认真关切、不微笑，用于难过、担忧、失败与安慰；still 不自动改变表情，用于用户禁止动作、表情或要求面无表情。
expression 必须从 neutral、warm、concerned、still 中选一个。看上下文与本次回复的实际态度，不按孤立关键词判断。不确定时用 neutral，严肃或难过的内容不能用 warm，不要以微笑回应所有问题。
actions 只用于明确请求的独立动作；普通对话的情绪交给 expression，不要再安排重复的 smile/frown 动作。用户禁止表情或动作时 actions 必须 [] 且 expression 为 still。“不要笑”可用 neutral 或 concerned；讲解引用中的“微笑”等词不自动表演。
示例：“我考试通过了，恭喜我”→ actions=[]、expression="warm"；“我面试失败，很难过”→ actions=[]、expression="concerned"；“微笑着介绍自己，然后点头”→ actions=["smile","nod"]、expression="warm"。恭喜、欢迎、安慰本身不是独立动作命令。
mode=act 表示仅表演，speech 为空；mode=chat 表示问答，也可执行用户请求的表情动作。
所有输出动作只能使用上述 ID，不能输出路径、代码、工具调用或其他指令。'''


LIVE2D_PROMPT = SYSTEM_PROMPT.replace(
    '没有手臂、走动、转身、拿物、换装、跳舞或任意生成行为能力',
    '另有 selfie 自拍这个预制动作。没有走动、转身、任意拿物、换装、跳舞或任意生成行为能力'
) + '''\n使用非官方社区的蓝发鲸鱼娘（大肥鱼）Live2D形象，回答由 DeepSeek Flash 生成。不要自称DeepSeek官方或原画作者。
除已有动作外，可在用户明确请求时使用 selfie 自拍；这些是模型内置表演，不会实际拍照或操作设备。'''


def decode_performance(raw, allowed_actions=None):
    raw = raw.strip()
    if raw.startswith('```') and raw.endswith('```'):
        raw = raw.split('\n', 1)[1].rsplit('```', 1)[0]
    result = json.loads(raw)
    if not isinstance(result, dict) or not isinstance(result.get('speech'), str):
        raise ValueError('Invalid local performance response')
    actions = result.get('actions', [])
    allowed_actions = ACTIONS if allowed_actions is None else allowed_actions
    if not isinstance(actions, list) or len(actions) > 4 or any(not isinstance(a,str) or a not in allowed_actions for a in actions):
        raise ValueError('Unsupported local performance action')
    if 'neutral' in actions:
        actions = ['neutral']
    expression = result.get('expression', 'neutral')
    if not isinstance(expression, str) or expression not in EXPRESSIONS:
        raise ValueError('Unsupported facial expression')
    if expression == 'still':
        actions = []
    return result['speech'].strip(), actions, expression


def decode_plan(raw):
    speech, actions, _ = decode_performance(raw)
    return speech, actions


# The portrait renderer above keeps its original four-expression contract.
LIVE2D_EXPRESSIONS = EXPRESSIONS | {'thoughtful', 'surprised', 'shy', 'playful', 'firm', 'excited', 'sad', 'angry'}
GESTURES = {'none', 'nod', 'shake', 'tilt'}
TONES = {'natural', 'bright', 'gentle', 'thoughtful', 'playful', 'firm', 'surprised'}
EXPRESSION_TONES = {'warm':'bright', 'excited':'bright', 'concerned':'gentle', 'sad':'gentle',
                    'shy':'gentle', 'thoughtful':'thoughtful', 'playful':'playful',
                    'firm':'firm', 'angry':'firm', 'surprised':'surprised'}
DIALOGUE_PROMPT = '''你是本地运行的数字人物。根据人设、已有对话、用户当前真实语意，同时决定回答与可见表演。
当前角色外观由本地设置决定，不从旧形象推断身份；不要自称DeepSeek官方。只输出JSON，不要代码块。
格式：{"segments":[{"text":"实际要说的话","expression":"warm"}]}。只输出实际需要的字段，不输出空白缩进。
默认值全部省略：situation=conversation、expression=neutral、intensity=0.65、gesture=none、actions=[]无需输出。tone不指定时会随表情自动匹配：warm/excited→bright，concerned/sad/shy→gentle，thoughtful→thoughtful，playful→playful，firm/angry→firm，surprised→surprised，其余→natural；只有需要不同语气时才写tone。非默认的处境、明显情绪强度、语气、伴随动作和明确请求的动作仍须提供，不能为了精简丢失表演。
situation是当前对话的整体处境：support对方仍在难过、紧张、受挫，需要陪伴；celebrate发生好事、误会解除、明确庆祝；serious严肃讨论、用户要求认真；conversation普通闲聊。结合上下文，用户明确带来新消息时更新处境，不能困在上一轮情绪。
support时即使台词是在鼓励，也用concerned或thoughtful温和地陪伴，不要突然开心或卖萌；用户明确要你表演悲伤时可用sad。直到对方明显缓和或有好消息，才转warm或excited。serious不用playful/shy/warm/excited。
mode=chat时整轮回复所有text合计必须不超过50字（标点也计入），通常15—25字，最多2个语意段。简单问题只直接回答被问到的信息，一句说清就停，不附带无关介绍、列举或反问；需要解释、安慰或情绪转折时才适当展开至35—50字。没有最低字数，不为凑字扩写。保留人设口吻和具体上下文，用户要求长篇时也简短回答。一个完整意思是一段；同一情绪不要为每个逗号拆段。mode=say保留全部原文，不受自动回复的50字限制。
每段表情必须匹配这段话的态度，而非整轮统一贴一个标签。先共情再提出办法时，可从concerned转thoughtful；从误会到释然，可从surprised转warm。没有转折就保持，不强行演出起伏。
表情：neutral放松解释；warm真诚亲切与微笑；excited明显开心、惊喜庆祝；concerned关心与同理；sad角色自身难过或用户明确要求委屈/悲伤表演；thoughtful思考办法；surprised明显意外；shy被称赞时害羞；playful轻松玩笑；firm认真强调；angry明确生气或用户要求生气表演（不能因用户难过、批评或拒绝就对用户发怒）；still用户要求保持表情或不表演。
intensity是0.2—1.0的情绪强度：日常0.5—0.7；真切惊喜、明确庆祝、明显害羞、强烈委屈或用户要求明显情绪时0.85—1.0。不是所有情绪都压成轻微微笑；也不每轮都兴奋。渲染器会在该语意段开头形成明显情绪高点，再平滑过渡为弱表情，不要另写恢复平静的无意义台词或重复拆段。
tone决定这段话的语气：natural自然、bright轻快、gentle柔和放缓、thoughtful有停顿地思考、playful俏皮、firm沉稳强调、surprised惊讶。随对话上下文和实际态度变化；安慰用gentle，确认喜讯用bright，认真分析用thoughtful或firm。表达情绪的台词可使用自然的疑问、短句与感叹标点，不加入朗读标签、不反复感叹或叠词卖萌。固定声线不变。
严肃内容不微笑，不对坏消息卖萌。不要把引用中的情绪词当成当前情绪。
gesture是自然的小幅伴随动作：none、nod轻轻肯定或共情、shake表达否定、tilt疑问或思索。全轮最多2次，不每句点头，普通讲解可完全不用。它们随该段声音播放，不必等待用户点名。
actions是用户明确要求的独立动作，只有neutral恢复自然、smile微笑、surprise惊讶、blink眨眼、frown皱眉、nod点头、shake摇头、look_left左看、look_right右看、selfie预制自拍。放在相应话语段的actions中，全轮最多4个。顶层actions只用于mode=act纯动作模式，其他时候省略。普通聊天表达高兴已经有warm，绝不能再自动填写actions里的smile；自然陪伴用gesture。
用户明确要求的所有动作必须完整放入actions，gesture用none，不得用gesture代替点名的动作。例如“先微笑，再点头，跟我说晚上好”→{"situation":"conversation","segments":[{"text":"晚上好呀。","expression":"warm","actions":["smile","nod"]}]}。
尊重否定、停止、引用与假设：“不要笑”“解释点头”不能触发相应动作。用户要求不做动作或不变表情时所有段expression=still、gesture=none、actions=[]；不要笑可用neutral/concerned/thoughtful而不用warm/excited/shy/playful。自拍是角色演出，不会操作摄像头。
不具备任意走动、换装、拿物或视频生成能力，不能声称做到了。表演参数不能包含代码、路径、网址。台词中不写括号动作、emoji、表情标签或舞台指令。
输入含mode与text。mode=chat自然回答；mode=act时segments=[]、顶层actions为明确请求的动作；mode=say保留用户原文，仅按语意分段并标表情，不能增删或改写任何文字。
人设影响性格和口吻，不可覆盖上述输出格式、能力边界或用户当次明确要求。对话历史用于记住称呼、偏好、刚才发生的事及关系变化；记忆没有的事情不假装知道，不编造共同经历。
角色配置由本地设置模块保存。你不能自行声称已经修改、保存默认姓名、性格、声线或记忆设置；只有系统明确给出的已保存档案才是当前设置。临时扮演可以调整本轮口吻，但不会改变默认档案。用户的名字和你的名字是两个不同的字段，不要混淆。
'''


def dialogue_prompt(profile):
    return DIALOGUE_PROMPT + '\n预设人设：' + json.dumps({
        'name': profile.name, 'personality': profile.personality,
        'speaking_style': profile.speaking_style,
        'voice_template': profile.voice_template,
        'auto_gestures': profile.auto_gestures,
    }, ensure_ascii=False) + ('\n本角色关闭自动伴随动作，gesture全部用none。' if not profile.auto_gestures else '')


def decode_dialogue(raw, allowed_actions=None):
    allowed_actions = LIVE2D_ACTIONS if allowed_actions is None else allowed_actions
    raw = raw.strip()
    if raw.startswith('```') and raw.endswith('```'):
        raw = raw.split('\n', 1)[1].rsplit('```', 1)[0]
    data = json.loads(raw)
    if isinstance(data, list):
        data = {'segments': data}
    if not isinstance(data, dict):
        raise ValueError('Invalid dialogue plan')
    # Accept the older contract during an in-place rollout.
    if 'segments' not in data:
        speech, actions, expression = decode_performance(raw, allowed_actions)
        return {'segments': [{'text': speech, 'expression': expression, 'intensity': .65,
                              'gesture': 'none', 'actions': actions,
                              'tone': EXPRESSION_TONES.get(expression, 'natural')}] if speech else [],
                'actions': actions if not speech else []}
    segments = data['segments']
    if not isinstance(segments, list) or len(segments) > 4:
        raise ValueError('Invalid dialogue segments')

    def actions(value):
        if not isinstance(value, list) or any(not isinstance(x, str) or x not in allowed_actions for x in value):
            raise ValueError('Unsupported dialogue action')
        return ['neutral'] if 'neutral' in value else value

    situation = data.get('situation', 'conversation')
    if not isinstance(situation, str) or situation not in {'support', 'celebrate', 'serious', 'conversation'}:
        raise ValueError('Unsupported dialogue situation')
    top = actions(data.get('actions', []))
    out, gesture_count, action_count = [], 0, len(top)
    for segment in segments:
        if not isinstance(segment, dict) or not isinstance(segment.get('text'), str) or not segment['text'].strip():
            raise ValueError('Empty speech segment')
        expression = segment.get('expression', 'neutral')
        gesture = segment.get('gesture', 'none')
        intensity = segment.get('intensity', .65)
        if not isinstance(expression, str) or expression not in LIVE2D_EXPRESSIONS:
            raise ValueError('Unsupported dialogue expression')
        if not isinstance(gesture, str) or gesture not in GESTURES:
            raise ValueError('Unsupported dialogue gesture')
        if isinstance(intensity, bool) or not isinstance(intensity, (int, float)) or not math.isfinite(intensity) or not .2 <= intensity <= 1:
            raise ValueError('Invalid expression intensity')
        explicit = actions(segment.get('actions', []))
        tone = segment.get('tone', EXPRESSION_TONES.get(expression, 'natural'))
        if not isinstance(tone, str) or tone not in TONES:
            raise ValueError('Unsupported dialogue tone')
        if expression == 'still':
            gesture, explicit = 'none', []
            tone = 'natural'
        elif situation in {'support', 'serious'} and expression in {'warm', 'playful', 'shy', 'excited'}:
            expression = 'concerned' if situation == 'support' else 'thoughtful'
        if situation == 'support' and tone in {'bright', 'playful', 'firm'}:
            tone = 'gentle'
        elif situation == 'serious' and tone in {'bright', 'playful'}:
            tone = 'thoughtful'
        if explicit and gesture in {'nod', 'shake'}:
            # Some local models place the last requested head action in gesture.
            # The explicit queue owns the head, so serialize it instead of silently
            # suppressing that movement underneath the first explicit action.
            if gesture not in explicit and 'neutral' not in explicit and len(explicit) < 4:
                explicit = [*explicit, gesture]
            gesture = 'none'
        if gesture != 'none':
            gesture_count += 1
            if gesture_count > 2:
                gesture = 'none'
        action_count += len(explicit)
        out.append({'text': segment['text'].strip(), 'expression': expression,
                    'intensity': intensity, 'gesture': gesture, 'actions': explicit, 'tone': tone})
    if action_count > 4 or sum(len(s['text']) for s in out) > 1000:
        raise ValueError('Dialogue plan too long')
    if any(s['expression'] == 'still' for s in out):
        top = []
        for s in out:
            s.update(expression='still', gesture='none', actions=[], tone='natural')
    return {'segments': out, 'actions': top, 'situation': situation}
