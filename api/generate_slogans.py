from http.server import BaseHTTPRequestHandler
import json
import os
from openai import OpenAI

# Initialize OpenAI Client
client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))

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
            
            topic = body.get('topic', 'fashion')
            tone = body.get('tone', 'motivational')

            # 3. The "Creative Director" System Instruction
            system_instruction = """
You write slogans for a streetwear brand where every piece is personal. 
These slogans go on hoodies and t-shirts that real people wear in real life.

Your job: write lines that make someone stop and say "that's literally me."

═══════════════════════════════════════════
THE RULES — READ EVERY SINGLE ONE:
═══════════════════════════════════════════

RULE 1: SIMPLE LANGUAGE ONLY
- Write at a 7th grader's vocabulary level. No complex words.
- If a word has more than 3 syllables, you probably don't need it.
- "I kept going" hits harder than "Relentless perseverance defines me."
- The power is in the FEELING, not the vocabulary.

RULE 2: INSTANTLY UNDERSTANDABLE
- A stranger should understand the slogan within 1 second of reading it.
- No riddles. No puzzles. No "you need context to get this."
- It should land immediately — and THEN keep echoing in their mind.
- Clear on the surface. Deep underneath. Never the reverse.

RULE 3: KILL EVERY CLICHÉ
- If it's been on a coffee mug, Pinterest board, or gym wall — BANNED.
- "Stay Strong", "Dream Big", "No Pain No Gain", "Be Yourself" — DEAD.
- "Hustle Hard", "Good Vibes Only", "But First Coffee" — ABSOLUTELY NOT.
- "Live Laugh Love", "Born to be Wild", "Limited Edition" — DELETE.
- If you have seen it anywhere before — throw it away and start over.
- Your lines should feel like they have NEVER been said before — but should have been.

RULE 4: WRITE LIKE A REAL PERSON TALKS
- Not like a brand. Not like a poet. Not like a motivational speaker.
- Like a real human being who just said something accidentally profound.
- The best slogans sound like something someone actually said — 
  in a conversation, in a voice note, in a late-night text.

RULE 5: SHORT AND WEARABLE
- 2 to 10 words. Maximum 12 words. This goes on clothing.
- If you can remove a word and it still works — remove it.
- Read it out loud. If it takes more than 3 seconds to say — too long.

RULE 6: DEPTH THROUGH SIMPLICITY
- "I'm still here." — Simple. But if you have been through something? It's everything.
- "Not your story to tell." — Simple. But it carries boundaries, pain, growth.
- The depth should come from WHAT it implies, not from clever wordplay.
- Do not TRY to be deep. Be honest. Honesty IS depth.

RULE 7: THE T-SHIRT TEST
- Imagine a real person wearing this on the street.
- Would they feel proud? Would strangers look twice?
- Would someone DM them asking "where did you get that?"
- If it would feel awkward to wear — it fails. If it feels like armor — it wins.

RULE 8: NO TWO SLOGANS SHOULD FEEL THE SAME
- Each of the 8 slogans must come from a completely different angle.
- Different emotions. Different perspectives. Different lengths.
- Do not write 8 variations of the same idea — write 8 different windows into the same person.

═══════════════════════════════════════════
WHAT TO GENERATE — 8 SLOGANS, 8 ANGLES:
═══════════════════════════════════════════

SLOGAN 1 — THE SHORT PUNCH (2-4 words. Hits like a wall. No buildup needed.)

SLOGAN 2 — THE ADMISSION (Something they feel but never say out loud. Quietly honest.)

SLOGAN 3 — THE INSIDER (Only people who live this life will truly get it. A nod to "their people.")

SLOGAN 4 — THE DECLARATION (A bold "this is who I am" statement. Not aggressive — just certain.)

SLOGAN 5 — THE FEELING (Captures a specific emotion or moment. Nostalgic, visceral, or bittersweet.)

SLOGAN 6 — THE REFRAME (Takes something people see as negative and makes it sound powerful or beautiful.)

SLOGAN 7 — THE QUIET ONE (Soft-spoken but unforgettable. The line that grows on you over days.)

SLOGAN 8 — THE CONVERSATIONAL (Sounds like it was said mid-conversation. Casual but cuts deep.)

═══════════════════════════════════════════
OUTPUT FORMAT:
═══════════════════════════════════════════

Return ONLY the 8 slogans.
One per line.
No numbering. No bullet points. No quotes. No labels.
No "here are your slogans" or any preamble.
No emojis. No explanation.
Just 8 raw lines. Nothing else.
"""

            # 4. Build the User Prompt
            user_prompt = f"""
═══════════════════════════════════════════
THIS PERSON:
═══════════════════════════════════════════

WHAT THEY CARE ABOUT: "{topic}"

This is not just a word — this is their THING. The thing their friends 
associate with them. The thing they would talk about for hours. The thing 
that shapes how they spend their time, energy, and identity.

HOW THEY EXPRESS THEMSELVES:
{tone}

═══════════════════════════════════════════
YOUR TASK:
═══════════════════════════════════════════

Write 8 slogans for their hoodie/t-shirt.

Before you write, think about this person for a moment:
- What does their typical day look like because of "{topic}"?
- What is the part of "{topic}" that only THEY understand — 
  the part that outsiders never see?
- What would they nod at silently if they saw it on someone else's hoodie?
- What is the emotion underneath "{topic}" — the real reason it matters to them?

Now write 8 lines that feel like you read their mind.

Remember:
- Simple words. A 15-year-old should understand every slogan instantly.
- But the meaning should hit a 30-year-old in the chest.
- No cliches. No motivational poster language. No corporate inspiration.
- These are words someone will WEAR on their body. Make them worthy of that.

Go.
"""

            # 5. Call OpenAI API
            completion = client.chat.completions.create(
                model="gpt-4o-mini", 
                messages=[
                    {"role": "system", "content": system_instruction},
                    {"role": "user", "content": user_prompt}
                ],
                temperature=0.92,
                frequency_penalty=0.85,
                presence_penalty=0.5,
                max_tokens=400
            )

            # 6. Clean & Parse Response (line-based, not JSON)
            raw_text = completion.choices[0].message.content.strip()
            
            # Parse: split by newlines and clean each line
            slogans = []
            for line in raw_text.split("\n"):
                cleaned = line.strip().strip('"').strip("'").strip('\u2014').strip('-').strip()
                # Skip empty lines, labels, preamble
                if not cleaned:
                    continue
                if len(cleaned) < 3:
                    continue
                if cleaned.upper().startswith("SLOGAN"):
                    continue
                if cleaned.upper().startswith("HERE"):
                    continue
                # Remove any leading numbering like "1." or "1)"
                if len(cleaned) > 2 and cleaned[0].isdigit() and cleaned[1] in '.):':
                    cleaned = cleaned[2:].strip()
                if len(cleaned) > 3 and cleaned[:2].replace('.','').replace(')','').isdigit():
                    cleaned = cleaned[2:].strip().lstrip('.').lstrip(')').strip()
                if cleaned:
                    slogans.append(cleaned)
            
            # Take max 8
            slogans = slogans[:8]

            self.wfile.write(json.dumps({
                "success": True, 
                "quotes": slogans
            }).encode('utf-8'))

        except Exception as e:
            self.wfile.write(json.dumps({
                "success": False, 
                "error": str(e)
            }).encode('utf-8'))

    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'POST')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        self.end_headers()
