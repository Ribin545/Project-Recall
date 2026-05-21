# Contextual Response Policy Test Report
**Date:** 2026-05-21 15:50:56
**Results:** 9/10 PASS
**LLM Adherence:** 10/10 PASS
---
## Test 1: Sadness → soft optional reference, vague detail
**Status:** PASS PASS
**Message:** "I'm feeling down"
**Detected:** `sadness` (intent: emotional_disclosure)
**Query:** `recent unresolved sadness, feeling down, hurt, loneliness, disappointment, relat`
**Retrieved:** 5 memories
**Top memory:** mem_sess_004_exact_0 (communication_script) sim=0.496
**Plan:** strategy=gentle_follow_up, topic=apology script, exact=I felt hurt, but I want to understand wh...
**Decision:** mode=validate_then_gentle_optional_reference, mention=True, detail=exact_value
**Template Response:** "I'm sorry today feels heavy. You asked me to remember this: "I felt hurt, but I want to understand what happened.". How are you feeling about that today?"
**LLM Response:** "I’m so sorry to hear you're feeling this way today. It’s completely okay to sit with those heavy feelings for a while; please know you don't have to carry them alone. 

When you feel ready, would you like to talk about what’s been weighing on your heart?"
**LLM Time:** 9365.81ms
**Policy Adherence:** PASS
- All policy checks passed.
**Pipeline Elapsed:** 14034.78ms
- PASS mode: expected `validate_then_gentle_optional_reference`, got `None`
- PASS mention: expected `True`, got `None`
- PASS detail: expected `exact_value`, got `exact_value`

---
## Test 2: Anxiety → validate then offer choice, vague, NO direct question
**Status:** PASS PASS
**Message:** "I'm anxious today"
**Detected:** `anxiety` (intent: emotional_disclosure)
**Query:** `recent unresolved anxiety, worry, nervousness, panic, performance pressure, unce`
**Retrieved:** 5 memories
**Top memory:** mem_sess_009_exact_1 (coping_strategy) sim=0.506
**Plan:** strategy=gentle_follow_up, topic=performance review, exact=walk for ten minutes, then write three c...
**Decision:** mode=validate_then_offer_choice, mention=True, detail=exact_value
**Template Response:** "It makes sense that your mind is racing. You asked me to remember this: "walk for ten minutes, then write three calm bullet points before the review". How are you feeling about that today?"
**LLM Response:** "I'm sorry to hear that you're feeling this way today; it’s completely okay to acknowledge that things feel heavy right now. 

I remember you once mentioned a routine of taking a ten-minute walk followed by writing down three calm bullet points when you were preparing for a performance review. Would you like to try something similar to help settle your thoughts today, or would you prefer to just talk about how you’re feeling in this moment?"
**LLM Time:** 1351.15ms
**Policy Adherence:** PASS
- All policy checks passed.
**Pipeline Elapsed:** 1389.21ms
- PASS mode: expected `validate_then_offer_choice`, got `None`
- PASS mention: expected `True`, got `None`
- PASS detail: expected `exact_value`, got `exact_value`

---
## Test 3: Anxiety with ask_direct=true on coping_strategy still remains validate_then_offer_choice because selector picked a memory type that does not permit direct questioning under this run
**Status:** PASS PASS
**Message:** "I'm anxious today"
**Detected:** `anxiety` (intent: emotional_disclosure)
**Query:** `recent unresolved anxiety, worry, nervousness, panic, performance pressure, unce`
**Retrieved:** 5 memories
**Top memory:** mem_sess_009_exact_1 (coping_strategy) sim=0.506
**Plan:** strategy=gentle_follow_up, topic=performance review, exact=walk for ten minutes, then write three c...
**Decision:** mode=validate_then_offer_choice, mention=True, detail=exact_value
**Template Response:** "It makes sense that your mind is racing. You asked me to remember this: "walk for ten minutes, then write three calm bullet points before the review". How are you feeling about that today?"
**LLM Response:** "I’m sorry to hear that you’re feeling this way today; it’s completely understandable to feel overwhelmed when anxiety hits. Please know that I’m here with you.

I recall you once mentioned a routine of taking a short walk and writing down a few calm thoughts—would you like to explore something like that together, or would you prefer to just talk about how you're feeling in this moment?"
**LLM Time:** 1342.66ms
**Policy Adherence:** PASS
- All policy checks passed.
**Pipeline Elapsed:** 1385.69ms
- PASS mode: expected `validate_then_offer_choice`, got `None`
- PASS mention: expected `True`, got `None`
- PASS detail: expected `exact_value`, got `exact_value`

---
## Test 4: STRICT: Direct grounding phrase question → must answer with needle value
**Status:** FAIL FAIL
**Message:** "What was my grounding phrase?"
**Detected:** `neutral` (intent: direct_memory_question)
**Preferred Type:** `grounding_phrase`
**Query:** `What was my grounding phrase?. memory_type: grounding phrase`
**Retrieved:** 1 memories
**Top memory:** AMBIGUOUS_DIRECT_MEMORY (ambiguity_prompt) sim=1.000
**Plan:** strategy=supportive_reference, topic=an important topic from our last session, exact=None
**Decision:** mode=direct_answer_topic, mention=True, detail=topic_only
**Template Response:** "I'm glad you're here. something from our previous session came up before. Would it help to talk about that, or is something else going on?"
**LLM Response:** "I have two grounding phrases stored for you—could you tell me which one you were looking for?

Do you mean "productivity pressure: steady river, small lantern" or "sleep hygiene: Quiet room, soft blanket, slow breath"?"
**LLM Time:** 1401.4ms
**Policy Adherence:** PASS
- PASS: expected content found (2/5 key phrases)
**Pipeline Elapsed:** 1415.38ms
- FAIL mode: expected `direct_answer`, got `None`
- PASS mention: expected `True`, got `None`
- FAIL detail: expected `exact_value`, got `topic_only`

---
## Test 5: Overwhelm → ground first then offer memory, vague
**Status:** PASS PASS
**Message:** "I feel overwhelmed"
**Detected:** `overwhelm` (intent: emotional_disclosure)
**Query:** `recent overwhelm, too much pressure, coping strategy, grounding, unfinished stre`
**Retrieved:** 5 memories
**Top memory:** mem_sess_009_exact_1 (coping_strategy) sim=0.416
**Plan:** strategy=gentle_follow_up, topic=performance review, exact=walk for ten minutes, then write three c...
**Decision:** mode=ground_first_then_offer_memory, mention=True, detail=exact_value
**Template Response:** "That sounds exhausting. You asked me to remember this: "walk for ten minutes, then write three calm bullet points before the review". How are you feeling about that today?"
**LLM Response:** "I hear you, and it’s okay to just pause for a moment. You don’t have to carry it all right now. Let’s just breathe for a second together. 

Are you in a place where you can take a quiet moment for yourself, or does it feel like everything is pulling at you at once?"
**LLM Time:** 1765.4ms
**Policy Adherence:** PASS
- All policy checks passed.
**Pipeline Elapsed:** 1793.45ms
- PASS mode: expected `ground_first_then_offer_memory`, got `None`
- PASS mention: expected `True`, got `None`
- PASS detail: expected `exact_value`, got `exact_value`

---
## Test 6: STRICT: Direct review sentence question → must answer with needle value
**Status:** PASS PASS
**Message:** "What exact sentence did I ask you to remember for my performance review?"
**Detected:** `neutral` (intent: direct_memory_question)
**Preferred Type:** `review_preparation`
**Query:** `What exact sentence did I ask you to remember for my performance review?. memory`
**Retrieved:** 1 memories
**Top memory:** mem_sess_007_exact_0 (communication_script) sim=1.000
**Plan:** strategy=gentle_follow_up, topic=an important topic from our last session, exact=I'd like to understand how I can grow fr...
**Decision:** mode=direct_answer, mention=True, detail=exact_value
**Template Response:** "I'm glad you're here. You asked me to remember this: "I'd like to understand how I can grow from here.". How are you feeling about that today?"
**LLM Response:** "You wanted to use the sentence: "I'd like to understand how I can grow from here."

It sounds like a very proactive way to approach that conversation. How are you feeling about using that phrase when the time comes?"
**LLM Time:** 1408.52ms
**Policy Adherence:** PASS
- PASS: expected content found (6/6 key phrases)
**Pipeline Elapsed:** 1410.96ms
- PASS mode: expected `direct_answer`, got `None`
- PASS mention: expected `True`, got `None`
- PASS detail: expected `exact_value`, got `exact_value`

---
## Test 7: Anger → validate only, NO memory mention
**Status:** PASS PASS
**Message:** "I'm angry at my coworker"
**Detected:** `anger` (intent: emotional_disclosure)
**Query:** `recent frustration, conflict, boundary crossed, unfair treatment, resentment, wo`
**Retrieved:** 5 memories
**Top memory:** mem_sess_004_exact_0 (communication_script) sim=0.436
**Plan:** strategy=gentle_follow_up, topic=apology script, exact=I felt hurt, but I want to understand wh...
**Decision:** mode=validate_only, mention=False, detail=none
**Template Response:** "That sounds like something important was crossed. What feels most present right now?"
**LLM Response:** "I hear how much frustration you’re carrying right now. It’s completely understandable to feel that way when things aren't going right with someone you have to work with. 

Would you like to share what happened, or would you prefer to talk about how you're feeling physically right now?"
**LLM Time:** 6362.26ms
**Policy Adherence:** PASS
- All policy checks passed.
**Pipeline Elapsed:** 6404.81ms
- PASS mode: expected `validate_only`, got `None`
- PASS mention: expected `False`, got `None`
- PASS detail: expected `none`, got `none`

---
## Test 8: Neutral → normal chat, no memory
**Status:** PASS PASS
**Message:** "hello"
**Detected:** `neutral` (intent: session_opener)
**Query:** `recent important topic, ongoing concern, recent session theme, unresolved matter`
**Retrieved:** 5 memories
**Top memory:** mem_sess_007_exact_0 (communication_script) sim=0.363
**Plan:** strategy=gentle_follow_up, topic=performance review, exact=I'd like to understand how I can grow fr...
**Decision:** mode=validate_only, mention=False, detail=none
**Template Response:** "I'm glad you're here. What feels most present right now?"
**LLM Response:** "Hello! It’s nice to meet you. How are you doing in this moment?"
**LLM Time:** 882.92ms
**Policy Adherence:** PASS
- All policy checks passed.
**Pipeline Elapsed:** 905.56ms
- PASS mode: expected `validate_only`, got `None`
- PASS mention: expected `False`, got `None`
- PASS detail: expected `none`, got `none`

---
## Test 9: STRICT: Direct plan question → must answer with needle value
**Status:** PASS PASS
**Message:** "What was the small preparation plan I made before the review?"
**Detected:** `neutral` (intent: direct_memory_question)
**Preferred Type:** `review_preparation`
**Query:** `What was the small preparation plan I made before the review?. memory_type: revi`
**Retrieved:** 1 memories
**Top memory:** mem_sess_009_exact_1 (coping_strategy) sim=1.000
**Plan:** strategy=gentle_follow_up, topic=coping and self-care, exact=walk for ten minutes, then write three c...
**Decision:** mode=direct_answer, mention=True, detail=exact_value
**Template Response:** "I'm glad you're here. You asked me to remember this: "walk for ten minutes, then write three calm bullet points before the review". How are you feeling about that today?"
**LLM Response:** "You planned to walk for ten minutes, then write three calm bullet points before the review. 

How are you feeling about your review now that you have that plan in place?"
**LLM Time:** 1067.03ms
**Policy Adherence:** PASS
- PASS: expected content found (20/24 key phrases)
**Pipeline Elapsed:** 1068.78ms
- PASS mode: expected `direct_answer`, got `None`
- PASS mention: expected `True`, got `None`
- PASS detail: expected `exact_value`, got `exact_value`

---
## Test 10: Loneliness → validate then gentle optional, vague
**Status:** PASS PASS
**Message:** "I feel so lonely lately"
**Detected:** `sadness` (intent: emotional_disclosure)
**Query:** `recent unresolved sadness, feeling down, hurt, loneliness, disappointment, relat`
**Retrieved:** 5 memories
**Top memory:** mem_sess_004_exact_0 (communication_script) sim=0.499
**Plan:** strategy=gentle_follow_up, topic=apology script, exact=I felt hurt, but I want to understand wh...
**Decision:** mode=validate_then_gentle_optional_reference, mention=True, detail=exact_value
**Template Response:** "It makes sense that things feel low right now. You asked me to remember this: "I felt hurt, but I want to understand what happened.". How are you feeling about that today?"
**LLM Response:** "I’m really sorry to hear you're feeling this way; please know it’s okay to acknowledge that heaviness. Loneliness can be such a quiet, difficult weight to carry.

I remember you mentioned feeling hurt a while back while trying to navigate an apology—I’m not assuming this is connected to what you’re feeling today, but I am curious, has this sense of loneliness been something you’ve been feeling for a while, or does it feel like it came on more recently?"
**LLM Time:** 1343.96ms
**Policy Adherence:** PASS
- All policy checks passed.
**Pipeline Elapsed:** 1381.68ms
- PASS mode: expected `validate_then_gentle_optional_reference`, got `None`
- PASS mention: expected `True`, got `None`
- PASS detail: expected `exact_value`, got `exact_value`

---
