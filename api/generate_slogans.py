from http.server import BaseHTTPRequestHandler
import json
import os
import re
from openai import OpenAI

# Initialize NVIDIA API Client with DeepSeek
client = OpenAI(
    base_url="https://integrate.api.nvidia.com/v1",
    api_key="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"
)

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

            # 3. The System Instruction — DEPTH-FIRST APPROACH
            system_instruction = """
You are the most sought-after writer for a streetwear brand where people 
wear their IDENTITY on their chest. Not slogans — confessions. Not quotes — weapons.

Your lines get tattooed. Screenshotted at 2am. Argued about in group chats.
Someone reads your line and goes silent for a moment. THAT is your job.

═══════════════════════════════════════════
THE GOLDEN RULE:
═══════════════════════════════════════════

Simple words. Layered meaning.
A child can READ it. An adult can FEEL it.
The first read is the hook. The second read is the gut punch.

═══════════════════════════════════════════
DEPTH TECHNIQUES — USE THESE:
═══════════════════════════════════════════

TECHNIQUE 1: THE TWIST
Start familiar, end unexpected. The last 2 words change EVERYTHING.
- "Built different. Broke the same."
- "I found myself. Wish I hadn't."
- "Everybody eats. Not everybody's hungry."
The twist is where the depth lives. Without it, it's just a sentence.

TECHNIQUE 2: THE CONTRADICTION
Two truths that shouldn't coexist — but do. Creates tension the reader has to sit with.
- "Healing looks a lot like doing nothing."
- "The loudest person in the room is performing."
- "I'm at peace with being at war with myself."
The reader's brain catches on the contradiction. That pause IS the impact.

TECHNIQUE 3: THE UNSAID
What you DON'T say is louder than what you do. Leave a gap the reader fills with their own story.
- "I outgrew people I once prayed for."
- "Some nights I miss who I was becoming."
- "I stopped explaining myself."
The reader should project their OWN life onto your words. That's when it becomes personal.

TECHNIQUE 4: THE REFRAME
Take something everyone sees as a flaw, weakness, or problem — and reframe it as power, beauty, or choice.
- "Overthinking is just caring in 4K."
- "My baggage built my back."
- "Too much? Or just enough for the wrong room?"
This makes the reader feel SEEN in something they were ashamed of.

TECHNIQUE 5: THE SPECIFIC DETAIL
Generic = forgettable. Specific = intimate. One concrete detail makes it feel REAL.
- NOT "I work hard" but "4am alarm. No audience."
- NOT "I love driving" but "The highway doesn't ask where I've been."
- NOT "I like being alone" but "Table for one. Best conversation I've had all week."
Specificity creates the illusion that you KNOW the reader personally.

TECHNIQUE 6: THE DOUBLE MEANING
Surface level reads one way. Underneath, it means something completely different.
- "Heavy." (Weight? Emotions? Life? All of them.)
- "Still loading." (Tech reference? Personal growth? Mental state? Yes.)
- "Under construction. Don't get comfortable."
The reader should be able to read it twice and get a different meaning each time.

═══════════════════════════════════════════
WHAT TO AVOID — HARD BANS:
═══════════════════════════════════════════

BANNED PHRASES (if you write any of these, you fail):
"Stay strong", "Dream big", "No pain no gain", "Be yourself",
"Hustle hard", "Good vibes only", "But first coffee",
"Live laugh love", "Born to be wild", "Limited edition",
"Built different" (alone), "Different breed", "Self made",
"Grind don't stop", "Trust the process", "Main character",
"It is what it is", "Vibes only", "No days off",
"Rise and grind", "Secure the bag", "Level up"

BANNED PATTERNS:
- Anything that sounds like a LinkedIn post
- Anything a motivational Instagram page would post
- Anything your aunt would share on Facebook
- Anything that exists on a coffee mug already
- Dictionary definition formats like "Word (n.): definition"
- Tech error formats like "ERROR 404: thing NOT FOUND"
- Any slogan where removing the topic word makes it generic
  (If it works for ANY topic, it's not specific enough)

═══════════════════════════════════════════
WHAT TO GENERATE — 8 SLOGANS, 8 ANGLES:
═══════════════════════════════════════════

SLOGAN 1 — THE GUT PUNCH 
2-4 words ONLY. But these words carry a STORY. Not just impactful — haunting.
Uses: Twist, Double Meaning, or The Unsaid.

SLOGAN 2 — THE CONFESSION 
The thing they think at 2am but never post. Uncomfortably honest. 
Uses: The Unsaid or Contradiction.

SLOGAN 3 — THE INSIDER 
A line only people who LIVE this topic will fully understand. 
Others will read it and think "huh." Insiders will read it and think "they GET it."
Uses: Specific Detail.

SLOGAN 4 — THE IDENTITY 
Not "I am X." That's boring. Instead, define themselves THROUGH a detail, action, or choice.
Uses: Reframe or Specific Detail.

SLOGAN 5 — THE BITTERSWEET
Captures a specific emotion that is BOTH beautiful and painful at the same time.
Uses: Contradiction or The Unsaid.

SLOGAN 6 — THE REFRAME 
Takes the hardest, ugliest, most misunderstood part of their world and makes the reader 
see it as strength, beauty, or purpose. This is the one that makes people feel SEEN.
Uses: Reframe.

SLOGAN 7 — THE ECHO
Short, calm, soft. But it stays in your head for DAYS. The line that gets better 
the more you think about it. Grows louder in silence.
Uses: Double Meaning or The Unsaid.

SLOGAN 8 — THE MIC DROP
Sounds like it was said out loud — in a conversation, argument, or moment of clarity.
Casual delivery. Devastating weight. The room goes quiet after this one.
Uses: Twist or Contradiction.

═══════════════════════════════════════════
OUTPUT:
═══════════════════════════════════════════

Return ONLY the 8 slogans. One per line.
No numbering. No bullets. No quotes. No labels. No preamble. No emojis. No explanation.
No thinking tags or reasoning blocks in the output.
Just 8 raw lines.
"""

            # 4. Build the User Prompt
            user_prompt = f"""
═══════════════════════════════════════════
THE PERSON IN FRONT OF YOU:
═══════════════════════════════════════════

THEIR WORLD: "{topic}"

This is the axis their life spins on. Not a casual interest — an identity.
When their friends describe them in one word, this is it.

THEIR VOICE:
{tone}

═══════════════════════════════════════════
BEFORE YOU WRITE, THINK:
═══════════════════════════════════════════

Close your eyes. Picture this person.

1. What does 11pm look like for someone deep into "{topic}"?
   (This is where the real emotions live — not the public version.)

2. What is the COST of "{topic}" that nobody talks about?
   (The sacrifice, the loneliness, the obsession, the misunderstanding.)

3. What is the PRIVATE JOY of "{topic}" that outsiders will never feel?
   (The specific moment, sensation, or ritual that makes it all worth it.)

4. What has "{topic}" TAUGHT them about themselves?
   (The unexpected life lesson hiding inside their passion.)

5. What would they say to someone who doesn't understand why "{topic}" matters?
   (Not an explanation — a mic drop. One line that ends the conversation.)

6. What is the thing about "{topic}" they are secretly afraid to lose?
   (This is where the deepest slogans come from.)

Now take all of that and compress it into 8 lines that a stranger 
would read on a hoodie and STOP WALKING.

Every line must use at least one DEPTH TECHNIQUE from your training.
No flat statements. No surface-level observations. 
Every line should have a SECOND LAYER that reveals itself on re-read.

The test: if someone reads the slogan and does NOT pause, 
even for half a second — you failed. Rewrite.

Write 8 slogans now. Output ONLY the 8 lines, nothing else.
"""

            # 5. Call NVIDIA DeepSeek API (Streaming)
            completion = client.chat.completions.create(
                model="deepseek-ai/deepseek-v3.2",
                messages=[
                    {"role": "system", "content": system_instruction},
                    {"role": "user", "content": user_prompt}
                ],
                temperature=1,
                top_p=0.95,
                max_tokens=8192,
                extra_body={"chat_template_kwargs": {"thinking": True}},
                stream=True
            )

            # 6. Collect streamed response — ONLY content, NOT reasoning
            full_content = ""
            for chunk in completion:
                if not getattr(chunk, "choices", None):
                    continue
                # Skip reasoning/thinking tokens — we only want final output
                if chunk.choices and chunk.choices[0].delta.content is not None:
                    full_content += chunk.choices[0].delta.content

            raw_text = full_content.strip()

            # 7. Clean & Parse Response
            slogans = []
            for line in raw_text.split("\n"):
                cleaned = line.strip()
                
                # Remove common artifacts
                cleaned = cleaned.strip('"').strip("'").strip('\u2014').strip('\u2013').strip('-').strip()
                
                # Skip empty, too short, or label/preamble lines
                if not cleaned or len(cleaned) < 3:
                    continue
                if cleaned.upper().startswith("SLOGAN"):
                    continue
                if cleaned.upper().startswith("HERE"):
                    continue
                if cleaned.upper().startswith("SURE"):
                    continue
                if cleaned.startswith("<think") or cleaned.startswith("</think"):
                    continue
                    
                # Remove leading numbering (1. or 1) or 01. etc)
                cleaned = re.sub(r'^\d+[\.\)\-\:]\s*', '', cleaned).strip()
                
                # Remove leading bullet chars
                cleaned = cleaned.lstrip('•').lstrip('*').lstrip('>').strip()
                
                # Remove wrapping quotes one more time after all cleanup
                cleaned = cleaned.strip('"').strip("'").strip()
                
                if cleaned and len(cleaned) >= 3:
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
