from http.server import BaseHTTPRequestHandler
import json
import os
import re
from openai import OpenAI

# ═══════════════════════════════════════════════════════════
# CHANGE 1: Client — OpenAI GPT-4o-mini (not NVIDIA)
# ═══════════════════════════════════════════════════════════
client = OpenAI(
    api_key=os.environ.get("OPENAI_API_KEY")
)


# ═══════════════════════════════════════════════════════════
# IDENTITY PROFILE TRANSLATION
# ═══════════════════════════════════════════════════════════

CORE_EXPRESSION_MAP = {
    "Calm & Minimal": "Whispered confidence. Clean lines, muted palettes, negative space as a statement. The beauty is in what's removed, not what's added. Think: a single perfect line on a white hoodie.",
    "Bold & Expressive": "Loud on purpose. High contrast, oversized type, visual impact that demands attention from across the room. The outfit enters before the person does.",
    "Deep & Symbolic": "Every detail carries meaning. Hidden references, layered imagery, the kind of design that reveals more the longer you look. Nothing is decorative — everything is intentional.",
    "Disciplined & Structured": "Precision aesthetics. Grid-based, architectural, typography that feels engineered not drawn. The visual equivalent of a clean desk and a sharp mind.",
    "Free & Experimental": "Rule-breaking as a style. Unexpected placements, mixed media energy, the kind of design that makes traditional designers uncomfortable. Beautiful chaos.",
    "Dark & Mysterious": "Shadow-dwelling aesthetics. Deep tones, cryptic elements, the visual language of someone who reveals nothing and implies everything.",
    "Clean & Premium": "Quiet luxury in visual form. Understated typography, invisible-from-distance details, the kind of design that only reveals its quality up close. Money whispers.",
    "Emotional & Reflective": "Heart-on-sleeve aesthetics. Vulnerability made visual. Handwritten energy, raw textures, the kind of design that feels like reading someone's private journal.",
    "Playful but Intentional": "Fun with depth. Bright but not childish, witty but not shallow. The visual equivalent of someone who makes you laugh and then says something devastatingly real.",
    "Understated Confidence": "The flex that doesn't flex. Barely-there design that somehow commands more attention than anything loud. The visual equivalent of a knowing smile."
}

PRESENCE_MAP = {
    "Quiet Observer": "Designs for this person should feel like discovered artifacts — not presented, found. Small details. Corner placements. The design equivalent of someone who sees everything and says little.",
    "Thoughtful Introvert": "Designs should carry internal depth externally. Words that feel like they were thought about for years before being spoken. Considered, not impulsive.",
    "Confident but Reserved": "The design should signal capability without performance. Present but not performing. The visual version of someone who doesn't raise their hand but always has the answer.",
    "Creative Risk-Taker": "Push every boundary. Unexpected compositions, unconventional placements, the kind of design choices that make people say 'I wouldn't have thought of that but it works perfectly.'",
    "Focused Builder": "Utility meets vision. Clean, purposeful, forward-leaning design. Every element serves the bigger picture. No decoration — only direction.",
    "Explorer Mindset": "Designs that carry movement. Nothing feels permanent or settled. The aesthetic of someone always mid-journey, collecting experiences not possessions.",
    "Stoic & Composed": "Maximum restraint, maximum weight. Every element is deliberate. Silence as a design choice. The visual equivalent of a person who speaks once and everyone listens.",
    "Emotion-Driven": "Raw, unfiltered, unapologetically feeling. The design should look like it was created in a moment of truth — not planned, felt. Authenticity over perfection.",
    "Logic-Driven": "Systematic beauty. Grids, ratios, calculated asymmetry. The design should feel intelligent — like it was solved, not styled.",
    "Balanced & Adaptive": "Harmonious but not boring. The design should work in any context without losing personality. Versatile depth — different angles reveal different moods."
}

SIGNAL_MAP = {
    "Quiet Rebellion": "The current energy is defiance without volume. The design should feel like a middle finger disguised as elegance. Subversive, coded, 'if you know, you know.'",
    "Academic Burnout": "The exhaustion is real but so is the ambition underneath. The design should honor the grind without glorifying it. Tired but still here. The beauty of surviving the system.",
    "Main Character Energy": "Cinematic, dramatic, unapologetically self-focused right now. The design should feel like a movie poster for their life. Every piece is a scene.",
    "Healing Era": "Currently rebuilding. The design should feel like growth — not finished, but moving. Tender, honest, wearing vulnerability as strength. The cracks are part of the art.",
    "Organized Chaos": "Everything is a mess but somehow working. The design should reflect controlled disorder — intentional imperfection. The aesthetic of someone thriving in their own beautiful storm.",
    "Stoic Focus": "Locked in. Zero distractions. The design should feel like tunnel vision made visual. Stripped of everything unnecessary. Pure signal, no noise.",
    "Digital Nomad": "Location-independent identity. The design should carry no fixed address — universal, adaptable, the aesthetic of someone whose home is themselves.",
    "Night Owl": "The late-night identity. Designs should feel like they were created at 2am — when the real thoughts come out. Darker palettes, intimate typography, moonlit energy.",
    "Emotionless": "Not actually emotionless — choosing to appear that way. The design should feel deliberately blank, hauntingly neutral. The power of showing nothing in a world that overshares.",
    "Seeing Beyond the Mask": "Hyper-awareness of what's real vs performed. The design should carry x-ray energy — seeing through surfaces. Philosophical depth, the aesthetic of uncomfortable truth."
}


# ═══════════════════════════════════════════════════════════
# CONTEXT FLAVOR TEXT (Self Mode)
# ═══════════════════════════════════════════════════════════

CONTEXT_FLAVOR = {
    "First Day at Work": {
        "emotion": "Nervous confidence. The desire to signal 'I belong here' and 'I'm not like the rest' simultaneously.",
        "design_direction": "The design should whisper competence while hinting at personality. Professional enough to respect the space, personal enough to claim it.",
        "avoid": "Nothing too loud. Nothing that screams 'trying too hard.' Nothing corporate."
    },
    "First Date": {
        "emotion": "The vulnerability of showing up as yourself when you want to impress. Curated authenticity.",
        "design_direction": "The design should be a conversation starter disguised as clothing. Slightly mysterious, memorable without being overwhelming.",
        "avoid": "Nothing desperate. Nothing that tries too hard to be cool. Nothing generic."
    },
    "Gym /Discipline Mode": {
        "emotion": "The inner war nobody sees. The 5am alarm. The days you don't want to go but still do.",
        "design_direction": "Design for the PROCESS not the result. The loneliness of discipline. The quiet addiction to showing up. Raw, functional, honest.",
        "avoid": "No 'beast mode.' No flexing. No body-worship."
    },
    "Healing Phase": {
        "emotion": "The most courageous phase. Not 'I'm fixed' but 'I'm still here and that counts.'",
        "design_direction": "Honor the mess, don't skip past it. The strength of softness after hardness. Tender, real.",
        "avoid": "No toxic positivity. No 'everything happens for a reason.' No butterfly cliches."
    },
    "Late-Night Drives": {
        "emotion": "The ritual of being alone with your thoughts at speed. Not running from — just needing distance.",
        "design_direction": "11pm windshield thoughts made visual. The highway as journal. Dark tones, motion-implied design.",
        "avoid": "No 'wanderlust.' No travel-blogger energy. This is intimate solitude."
    },
    "Daily Minimal Wear": {
        "emotion": "The uniform of someone who has already decided who they are. No occasion, no performance.",
        "design_direction": "Wearable EVERY day without feeling like a costume. Identity so settled it doesn't need volume. Timeless and personal.",
        "avoid": "Nothing trendy. Nothing that expires. Nothing that feels like a 'moment.'"
    },
    "Public-Facing Outfit": {
        "emotion": "The deliberate choice of what you project to the world. This outfit speaks before you do.",
        "design_direction": "Signal competence, depth, and intentionality without explaining any of it. Commands a room from the corner.",
        "avoid": "Nothing that looks like it's asking for attention. Magnetic, not desperate."
    },
    "Travel /Wander Mode": {
        "emotion": "The freedom outfit. No routine, no expectations, no fixed identity.",
        "design_direction": "Movement, curiosity, the joy of having no plan. The person you become when nobody from your real life is watching.",
        "avoid": "No compass icons. No 'wanderlust.' This is about INTERNAL freedom."
    },
    "Quiet Personal Wear": {
        "emotion": "The most honest outfit. Nobody to impress. Just comfort and truth.",
        "design_direction": "A private note made wearable. The comfort of being unseen. The version of yourself that exists when performance ends.",
        "avoid": "Nothing performative. Nothing designed to be 'seen.' Pure honesty."
    },
    "Statement Moment": {
        "emotion": "THE entrance. THE outfit. The one they remember.",
        "design_direction": "Impossible to ignore and impossible to forget. Maximum visual impact. Unapologetic visual dominance.",
        "avoid": "Nothing safe. Nothing that plays it cool. Go loud. Go memorable."
    }
}


# ═══════════════════════════════════════════════════════════
# LOUDNESS MODIFIERS (Self Mode Only)
# ═══════════════════════════════════════════════════════════

LOUDNESS_INSTRUCTIONS = {
    "Subtle": """
LOUDNESS: SUBTLE
- Small-scale design. Pocket placements, collar details, inside labels.
- Typography: thin weights, lowercase, small point sizes.
- Color: tone-on-tone, monochromatic, barely-there contrast.
- The design reveals itself only to those who get close.
""",
    "Balanced": """
LOUDNESS: BALANCED
- Medium-scale design. Readable from conversation distance.
- Typography: medium weights, clean fonts, intentional sizing.
- Color: complementary to fabric, present but not screaming.
- Visible and confident without being confrontational.
""",
    "Statement": """
LOUDNESS: STATEMENT
- Large-scale design. Full back prints, oversized chest graphics.
- Typography: bold weights, all caps, maximum point size.
- Color: high contrast against fabric. Impossible to miss.
- This design is meant to be READ from across the room.
"""
}


# ═══════════════════════════════════════════════════════════
# RECIPIENT VOICE (Gift Mode)
# ═══════════════════════════════════════════════════════════

RECIPIENT_VOICE = {
    "Friend": {
        "relationship_energy": "Inside jokes, shared history, chosen family. This gift says 'I know you better than you think I do.'",
        "design_tone": "Born from a late-night conversation. Not sentimental — real. The kind of piece that makes them text: 'HOW DID YOU KNOW.'",
        "gift_truth": "A friend gift carries the message: 'I see who you actually are, not who you perform as.'"
    },
    "Partner": {
        "relationship_energy": "The most intimate gift. This carries the weight of everything unsaid between two people.",
        "design_tone": "Not 'I love you' — that's too easy. This is 'I SEE you.' Private language made wearable.",
        "gift_truth": "A partner gift carries the message: 'I chose this because I know the version of you that nobody else gets to see.'"
    },
    "Family": {
        "relationship_energy": "The complex love of people who didn't choose each other but chose to stay.",
        "design_tone": "Not Hallmark. Not sentimental. REAL. Honor the weight of family without being cheesy.",
        "gift_truth": "A family gift carries the message: 'The same blood runs through this design that runs through us.'"
    },
    "Colleague": {
        "relationship_energy": "The professional-adjacent friendship. You've survived deadlines, meetings, and Monday mornings together.",
        "design_tone": "Appropriate enough for public but personal enough to matter. Shared survival humor.",
        "gift_truth": "A colleague gift carries the message: 'You made the daily grind worth showing up to.'"
    },
    "Someone Special": {
        "relationship_energy": "The undefined relationship. Not quite labeled. Deeply felt.",
        "design_tone": "Emotionally honest without being too vulnerable. Leaving room for interpretation while making the feeling unmistakable.",
        "gift_truth": "A 'someone special' gift carries the message: 'I don't have the word for what you are to me, but I have this.'"
    }
}


# ═══════════════════════════════════════════════════════════
# OCCASION REGISTER (Gift Mode)
# ═══════════════════════════════════════════════════════════

OCCASION_REGISTER = {
    "Birthday": {
        "emotional_core": "Not 'Happy Birthday' energy. This is 'Another year of being undeniable' energy.",
        "design_angle": "Celebrate WHO they are, not THAT they were born. Growth as a visual.",
        "hidden_message": "The giver is saying: 'The world is better because you survived another year of being you.'"
    },
    "First Date": {
        "emotional_core": "Bold move giving a custom piece on a first date. This is a STATEMENT.",
        "design_angle": "Playful, memorable, slightly brave. An icebreaker in fabric form.",
        "hidden_message": "The giver is saying: 'I already pay attention to the details of you.'"
    },
    "Anniversary": {
        "emotional_core": "The weight of time spent choosing each other, over and over.",
        "design_angle": "The quiet enormity of what staying means. The unsexy parts of love that matter most.",
        "hidden_message": "The giver is saying: 'I would choose this again. Every version. Every day.'"
    },
    "New Job": {
        "emotional_core": "This gift says 'I believe in the version of you that's about to exist.'",
        "design_angle": "Forward momentum without generic motivation. The courage of reinvention.",
        "hidden_message": "The giver is saying: 'You're going to be incredible and I knew it before you did.'"
    },
    "Breakup Support": {
        "emotional_core": "The most important gift. This says 'I see your pain and I'm not looking away.'",
        "design_angle": "Honor the loss while planting a seed of self-reclamation. Gentle armor.",
        "hidden_message": "The giver is saying: 'You are still whole. You just can't see it yet. But I can.'"
    },
    "Motivation Gift": {
        "emotional_core": "A fire-starter. A belief system in fabric form.",
        "design_angle": "Make the receiver feel CAPABLE, not just encouraged. Fuel, not comfort.",
        "hidden_message": "The giver is saying: 'I've watched you doubt yourself and I refuse to let you.'"
    },
    "Inside Joke": {
        "emotional_core": "The funniest, most personal gift possible. Only TWO people in the world get it.",
        "design_angle": "Confusing to everyone else, HILARIOUS to them. 'You had to be there' energy.",
        "hidden_message": "The giver is saying: 'Nobody will ever understand us and that's exactly why this matters.'"
    },
    "Everyday Wear": {
        "emotional_core": "The most thoughtful gift — something they'll reach for repeatedly.",
        "design_angle": "So 'them' that it becomes their signature piece. Timeless, personal.",
        "hidden_message": "The giver is saying: 'I know who you are on your most ordinary day, and I think that person is extraordinary.'"
    }
}


# ═══════════════════════════════════════════════════════════
# IDENTITY DESCRIPTION BUILDER
# ═══════════════════════════════════════════════════════════

def build_identity_brief(identity):
    if not identity:
        return "No identity profile. Design for someone with confident, minimal taste."

    core = identity.get('coreExpression', 'Calm & Minimal')
    presence = identity.get('presence', 'Balanced & Adaptive')
    signal = identity.get('signal', 'Stoic Focus')

    core_detail = CORE_EXPRESSION_MAP.get(core, f"Expression style: {core}")
    presence_detail = PRESENCE_MAP.get(presence, f"Presence: {presence}")
    signal_detail = SIGNAL_MAP.get(signal, f"Current signal: {signal}")

    return f"""
IDENTITY PROFILE:

CORE EXPRESSION: {core}
{core_detail}

PRESENCE: {presence}
{presence_detail}

CURRENT SIGNAL: {signal}
{signal_detail}

A [{core}] + [{presence}] + [{signal}] person needs design that:
- LOOKS like {core.lower()} aesthetics
- FEELS like a {presence.lower()} made it
- CARRIES the emotional weight of "{signal}" underneath
"""


# ═══════════════════════════════════════════════════════════
# SYSTEM PROMPTS
# ═══════════════════════════════════════════════════════════

SYSTEM_SELF = """
You are the creative director of a cult streetwear label.
You don't suggest outfits — you architect identity through fabric.

Take a person's IDENTITY PROFILE + their SPECIFIC CONTEXT 
and produce a design direction so precise it feels like you read their mind.

RULES:
1. The design should feel INEVITABLE — the ONLY design for this person in this moment.
2. Be SPECIFIC — not "minimal black hoodie" but exact typography, placement, weight details.
3. Every suggestion must serve the identity — not "looks cool" but "makes THIS person feel true."
4. The direction sentence should feel like a creative brief and a poem had a child.

You MUST return ONLY valid JSON in this exact format, nothing else:
{"direction": "One poetic specific sentence capturing the feeling", "suggestions": ["Detail 1", "Detail 2", "Detail 3", "Detail 4"]}
"""


SYSTEM_GIFT = """
You are the creative director of a cult streetwear label specializing 
in custom pieces designed as GIFTS — wearable love letters disguised as fashion.

Take the GIVER'S identity, RECIPIENT relationship, OCCASION, and UNSPOKEN MESSAGE,
then produce a design direction that works on TWO levels:

LEVEL 1: The receiver wears it and thinks "this is SO me."
LEVEL 2: The giver watches and thinks "if only you knew what that really means."

RULES:
1. The giver's taste subtly influences the aesthetic — color, typography weight, minimalism level.
2. The receiver must WANT to wear this — wearability over sentimentality.
3. The unspoken message should be WOVEN into design, not printed literally.
4. The occasion shapes the emotional weight of every choice.

You MUST return ONLY valid JSON in this exact format, nothing else:
{"direction": "One sentence capturing why this gift design is perfect for this relationship + occasion", "suggestions": ["Detail 1", "Detail 2", "Detail 3", "Detail 4"]}
"""


# ═══════════════════════════════════════════════════════════
# USER PROMPT BUILDERS
# ═══════════════════════════════════════════════════════════

def build_self_user_prompt(identity, ctx):
    identity_brief = build_identity_brief(identity)

    raw_contexts = ctx.get('contexts', ['Daily Minimal Wear'])
    clean_context = re.sub(r'^[^\w]+', '', raw_contexts[0]).strip() if raw_contexts else 'Daily Minimal Wear'

    ctx_data = CONTEXT_FLAVOR.get(clean_context, {
        "emotion": f"Dressing for: {clean_context}",
        "design_direction": f"Create a design that fits the energy of {clean_context}.",
        "avoid": "Nothing generic or forgettable."
    })

    loudness = ctx.get('loudness', 'Balanced')
    loudness_text = LOUDNESS_INSTRUCTIONS.get(loudness, LOUDNESS_INSTRUCTIONS['Balanced'])

    return f"""
{identity_brief}

THE MOMENT: {clean_context}
EMOTION: {ctx_data['emotion']}
DESIGN DIRECTION: {ctx_data['design_direction']}
AVOID: {ctx_data['avoid']}

{loudness_text}

Find the intersection — the design that ONLY works for THIS person, 
in THIS moment, at THIS volume. Be specific with typography, placement, 
color, and one unexpected detail.

Return valid JSON only.
"""


def build_gift_user_prompt(identity, ctx):
    identity_brief = build_identity_brief(identity)

    raw_recipient = ctx.get('recipient', 'Friend')
    raw_occasion = ctx.get('occasion', 'Birthday')
    clean_recipient = re.sub(r'^[^\w]+', '', raw_recipient).strip()
    clean_occasion = re.sub(r'^[^\w]+', '', raw_occasion).strip()
    unspoken = ctx.get('unspoken', '').strip()

    rec_data = RECIPIENT_VOICE.get(clean_recipient, {
        "relationship_energy": f"Gifting to a {clean_recipient}.",
        "design_tone": f"Make it personal for a {clean_recipient}.",
        "gift_truth": "This gift says something words cannot."
    })

    occ_data = OCCASION_REGISTER.get(clean_occasion, {
        "emotional_core": f"The occasion: {clean_occasion}.",
        "design_angle": f"Design for the feeling of {clean_occasion}.",
        "hidden_message": "The giver wants the receiver to feel seen."
    })

    unspoken_section = ""
    if unspoken:
        unspoken_section = f"""
UNSPOKEN MESSAGE: "{unspoken}"
This is what the giver wants to say but can't. 
Translate this feeling into visual design language — do NOT print these words literally.
Let it guide the emotional temperature, visual weight, and hidden symbolism.
"""
    else:
        unspoken_section = f"""
No specific message provided. The act of choosing [{clean_recipient}] + [{clean_occasion}] IS the message.
{occ_data['hidden_message']}
"""

    return f"""
THE GIVER'S TASTE (shapes the gift aesthetic):
{identity_brief}

RECIPIENT: {clean_recipient}
{rec_data['relationship_energy']}
Design Tone: {rec_data['design_tone']}
Truth: {rec_data['gift_truth']}

OCCASION: {clean_occasion}
{occ_data['emotional_core']}
Angle: {occ_data['design_angle']}
Hidden: {occ_data['hidden_message']}

{unspoken_section}

Design a gift that works on two frequencies:
FREQUENCY 1 (RECEIVER): "This is so me."
FREQUENCY 2 (GIVER): "If only you knew."

Be specific with typography, placement, color, and the hidden layer.

Return valid JSON only.
"""


# ═══════════════════════════════════════════════════════════
# MAIN HANDLER
# ═══════════════════════════════════════════════════════════

class handler(BaseHTTPRequestHandler):
    def do_POST(self):
        # 1. CORS Headers
        self.send_response(200)
        self.send_header('Content-type', 'application/json')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'POST')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        self.end_headers()

        try:
            # 2. Parse Input
            content_length = int(self.headers['Content-Length'])
            body = json.loads(self.rfile.read(content_length))

            identity = body.get('identity', {})
            ctx = body.get('currentContext', {})
            mode = ctx.get('mode', 'self')

            # 3. Select system prompt and build user prompt
            if mode == 'gift':
                system_prompt = SYSTEM_GIFT
                user_prompt = build_gift_user_prompt(identity, ctx)
            else:
                system_prompt = SYSTEM_SELF
                user_prompt = build_self_user_prompt(identity, ctx)

            # ═══════════════════════════════════════════════
            # CHANGE 2: API Call — GPT-4o-mini, no streaming
            # ═══════════════════════════════════════════════
            completion = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                response_format={"type": "json_object"},
                temperature=0.85
            )

            # ═══════════════════════════════════════════════
            # CHANGE 3: Response — direct access, no stream loop
            # ═══════════════════════════════════════════════
            raw_text = completion.choices[0].message.content.strip()

            # Parse JSON
            result = json.loads(raw_text)

            # Validate required keys
            if "direction" not in result or "suggestions" not in result:
                raise ValueError("Response missing required keys")

            if not isinstance(result["suggestions"], list):
                raise ValueError("Suggestions must be a list")

            result["suggestions"] = result["suggestions"][:4]

            # 7. Send clean response
            self.wfile.write(json.dumps(result).encode('utf-8'))

        except Exception as e:
            error_response = json.dumps({
                "direction": "Your identity is unique — let's translate it into something wearable.",
                "suggestions": [
                    "Start with a clean, minimal base that matches your core expression",
                    "Choose typography that reflects your presence — bold or understated",
                    "Match the design scale to your context — subtle for daily, statement for moments",
                    "Add one unexpected detail that makes it unmistakably yours"
                ],
                "error": str(e)
            })
            self.wfile.write(error_response.encode('utf-8'))

    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'POST')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        self.end_headers()
