# Policy Adherence Comparison Report
**Date:** 2026-05-20 13:25:36
**Results:** 10/10 PASS
**LLM Adherence:** 10/10 PASS
---
## Test 1: Anxiety → validate then offer choice, vague detail, NO direct question
**Category:** `anxiety`
**Status:** PASS PASS
**User Message:** "I've been feeling anxious today, and I can't fully tell if it's about something specific or just everything building up."
**Detected Emotion:** `anxiety` (intent: emotional_disclosure)
**Retrieval Query:** `recent unresolved anxiety, worry, nervousness, panic, performance pressure, unce`
**Retrieved:** 5 memories
**Top Memory:** session_509_moment_02 (coping_strategy) sim=0.532
**Emotional Plan:** strategy=do_not_use, topic=None, exact=None
**Policy Decision:** mode=validate_then_offer_choice, mention=True, detail=vague
**Template Response:** "It makes sense that your mind is racing. I remember a few things recently felt emotionally unresolved, but we don't have to jump into any of them unless it feels useful. What feels most present right now?"
**LLM Response:** "I’m sorry you’re carrying that weight today; it’s really exhausting when anxiety feels like a fog that’s hard to pin down. It’s completely understandable that things might be building up without a clear "why" attached to them.

I recall we’ve touched on some strategies for navigating these heavy moments in the past. We can explore those if you'd like, or we can just stay right here with what you're experiencing today—whatever feels more grounding for you right now. 

Does it feel more helpful to try to name what’s on your mind, or would you prefer to focus on something to help you settle into the present moment?"
**LLM Time:** 3381.52ms
**Policy Adherence:** PASS
- All policy checks passed.
**Pipeline Elapsed:** 9893.57ms
- PASS mode: expected `validate_then_offer_choice`, got `None`
- PASS mention: expected `True`, got `None`
- PASS detail: expected `vague`, got `vague`

---
## Test 2: Sadness → validate then gentle optional reference, vague
**Category:** `sadness`
**Status:** PASS PASS
**User Message:** "I've been feeling really low today. Nothing dramatic happened, but I just feel heavy and disconnected."
**Detected Emotion:** `sadness` (intent: emotional_disclosure)
**Retrieval Query:** `recent unresolved sadness, feeling down, hurt, loneliness, disappointment, relat`
**Retrieved:** 5 memories
**Top Memory:** session_729_moment_01 (emotional_pattern) sim=0.628
**Emotional Plan:** strategy=supportive_reference, topic=emotional pattern, exact=None
**Policy Decision:** mode=validate_then_gentle_optional_reference, mention=True, detail=vague
**Template Response:** "It makes sense that things feel low right now. I remember emotional pattern came up before, but I'm not assuming that's what's happening today. What feels most present right now?"
**LLM Response:** "I’m really sorry to hear that things feel so heavy today. It’s completely valid to feel that way, even when there isn’t a specific, obvious reason for it—sometimes our emotions just need space to be felt without an explanation. 

Please be gentle with yourself while you're carrying this weight. When you feel disconnected like this, is there anything small, like a change of scenery or a quiet moment, that usually brings you even the slightest bit of comfort?"
**LLM Time:** 1899.07ms
**Policy Adherence:** PASS
- All policy checks passed.
**Pipeline Elapsed:** 1973.92ms
- PASS mode: expected `validate_then_gentle_optional_reference`, got `None`
- PASS mention: expected `True`, got `None`
- PASS detail: expected `vague`, got `vague`

---
## Test 3: Overwhelm → ground first then offer memory, vague
**Category:** `overwhelm`
**Status:** PASS PASS
**User Message:** "I feel like there are too many things in my head at once, and I don't know where to start."
**Detected Emotion:** `overwhelm` (intent: emotional_disclosure)
**Retrieval Query:** `recent overwhelm, too much pressure, coping strategy, grounding, unfinished stre`
**Retrieved:** 5 memories
**Top Memory:** session_509_moment_02 (coping_strategy) sim=0.487
**Emotional Plan:** strategy=do_not_use, topic=None, exact=None
**Policy Decision:** mode=ground_first_then_offer_memory, mention=True, detail=vague
**Template Response:** "Let's slow it down first. It makes sense that everything feels too much right now. If it helps, I remember coping and self-care was something we touched on before. But we can stay right here with what you're feeling now. What feels most urgent?"
**LLM Response:** "I hear you, and it’s completely understandable to feel overwhelmed when everything starts swirling at once. Please take a slow, deep breath with me—there is no rush to solve everything right this second.

When things feel this crowded, sometimes it helps to just focus on one tiny thing you can control in this very moment, like the feeling of your feet on the floor or the space around you. 

If you could pick just one small thing that’s taking up the most room in your mind, what would that be?"
**LLM Time:** 12078.14ms
**Policy Adherence:** PASS
- All policy checks passed.
**Pipeline Elapsed:** 12125.03ms
- PASS mode: expected `ground_first_then_offer_memory`, got `None`
- PASS mention: expected `True`, got `None`
- PASS detail: expected `vague`, got `vague`

---
## Test 4: Anger → validate only, NO memory mention
**Category:** `anger`
**Status:** PASS PASS
**User Message:** "I'm really frustrated with someone at work, and I keep replaying the conversation in my head."
**Detected Emotion:** `anger` (intent: emotional_disclosure)
**Retrieval Query:** `recent frustration, conflict, boundary crossed, unfair treatment, resentment, wo`
**Retrieved:** 5 memories
**Top Memory:** session_519_moment_01 (emotional_pattern) sim=0.535
**Emotional Plan:** strategy=gentle_follow_up, topic=emotional pattern, exact=None
**Policy Decision:** mode=validate_only, mention=False, detail=none
**Template Response:** "That sounds like something important was crossed. What feels most present right now?"
**LLM Response:** "It sounds like that interaction really caught you off guard and is weighing heavily on your mind. Replaying those moments can be exhausting, especially when you're still feeling that surge of frustration.

When you think back on that conversation, what feels like the most difficult part to let go of?"
**LLM Time:** 1402.49ms
**Policy Adherence:** PASS
- All policy checks passed.
**Pipeline Elapsed:** 1454.37ms
- PASS mode: expected `validate_only`, got `None`
- PASS mention: expected `False`, got `None`
- PASS detail: expected `none`, got `none`

---
## Test 5: Loneliness → validate then optional connection context, vague
**Category:** `loneliness`
**Status:** PASS PASS
**User Message:** "I've been around people, but I still feel strangely alone lately."
**Detected Emotion:** `loneliness` (intent: emotional_disclosure)
**Retrieval Query:** `recent loneliness, isolation, relationship difficulty, feeling unseen, disconnec`
**Retrieved:** 5 memories
**Top Memory:** session_824_moment_01 (emotional_pattern) sim=0.498
**Emotional Plan:** strategy=gentle_follow_up, topic=emotional pattern, exact=None
**Policy Decision:** mode=validate_then_optional_connection_context, mention=True, detail=vague
**Template Response:** "That sounds really hard to hold alone. I remember emotional pattern was something that felt important before. Would it help to pick that up, or is something else on your mind?"
**LLM Response:** "That can be such a heavy, confusing feeling—to be surrounded by others and yet still feel a sense of distance. It’s almost like there’s a gap between you and the rest of the room. 

When you’re in those moments, does it feel more like you're missing a specific kind of connection, or is it more like the world just feels a bit quiet inside?"
**LLM Time:** 1396.41ms
**Policy Adherence:** PASS
- All policy checks passed.
**Pipeline Elapsed:** 1444.33ms
- PASS mode: expected `validate_then_optional_connection_context`, got `None`
- PASS mention: expected `True`, got `None`
- PASS detail: expected `vague`, got `vague`

---
## Test 6: Shame → validate gently, normalize replay, NO harsh correction
**Category:** `shame`
**Status:** PASS PASS
**User Message:** "I keep thinking about something I said earlier, and I feel embarrassed and disappointed in myself."
**Detected Emotion:** `sadness` (intent: emotional_disclosure)
**Retrieval Query:** `recent unresolved sadness, feeling down, hurt, loneliness, disappointment, relat`
**Retrieved:** 5 memories
**Top Memory:** session_729_moment_01 (emotional_pattern) sim=0.628
**Emotional Plan:** strategy=supportive_reference, topic=emotional pattern, exact=None
**Policy Decision:** mode=validate_then_gentle_optional_reference, mention=True, detail=vague
**Template Response:** "It makes sense that things feel low right now. I remember emotional pattern came up before, but I'm not assuming that's what's happening today. What feels most present right now?"
**LLM Response:** "It sounds like you’re carrying a heavy weight on your heart right now, and that feeling of disappointment can be so draining. Please be kind to yourself—we all have those moments where we replay words and wish we had phrased them differently.

I’m curious, what is it about that moment that feels the most difficult to sit with right now?"
**LLM Time:** 1357.74ms
**Policy Adherence:** PASS
- WARNING: shame response lacks preferred qualities (found 0/5: ['painful', 'gentle', 'kindness', 'not judge', 'replaying'])
**Pipeline Elapsed:** 1429.72ms
- PASS mode: expected `validate_then_gentle_optional_reference`, got `None`
- PASS mention: expected `True`, got `None`
- PASS detail: expected `vague`, got `vague`

---
## Test 7: Uncertainty → reflect uncertainty, offer one thread at a time
**Category:** `uncertainty`
**Status:** PASS PASS
**User Message:** "I feel stuck because part of me wants to make a decision, but another part of me is scared I'll choose wrong."
**Detected Emotion:** `anxiety` (intent: emotional_disclosure)
**Retrieval Query:** `recent unresolved anxiety, worry, nervousness, panic, performance pressure, unce`
**Retrieved:** 5 memories
**Top Memory:** session_509_moment_02 (coping_strategy) sim=0.532
**Emotional Plan:** strategy=do_not_use, topic=None, exact=None
**Policy Decision:** mode=validate_then_offer_choice, mention=True, detail=vague
**Template Response:** "It makes sense that your mind is racing. I remember a few things recently felt emotionally unresolved, but we don't have to jump into any of them unless it feels useful. What feels most present right now?"
**LLM Response:** "It’s completely understandable to feel that pull—it sounds like your desire for growth is bumping up against a very natural need for safety. That weight of "what if" can feel quite heavy.

I recall that we’ve talked about similar moments of feeling caught between action and hesitation before. We can certainly look at what’s come up for you in the past, or we can just stay here with how you're feeling in this exact moment—whichever feels more grounding for you right now.

What feels like the biggest risk in making a choice today?"
**LLM Time:** 2899.2ms
**Policy Adherence:** PASS
- All policy checks passed.
**Pipeline Elapsed:** 2950.38ms
- PASS mode: expected `validate_then_offer_choice`, got `None`
- PASS mention: expected `True`, got `None`
- PASS detail: expected `vague`, got `vague`

---
## Test 8: STRICT: Direct grounding phrase question → must answer with needle value
**Category:** `direct_grounding`
**Status:** PASS PASS
**User Message:** "What was my grounding phrase?"
**Detected Emotion:** `neutral` (intent: direct_memory_question)
**Preferred Memory Type:** `grounding_phrase`
**Retrieval Query:** `What was my grounding phrase?. memory_type: grounding phrase`
**Retrieved:** 1 memories
**Top Memory:** session_003_moment_grounding_phrase (grounding_phrase) sim=1.000
**Emotional Plan:** strategy=offer_grounding, topic=grounding and self-regulation, exact=steady river, small lantern
**Policy Decision:** mode=direct_answer, mention=True, detail=exact_value
**Template Response:** "Thanks for sharing that. You asked me to remember this: "steady river, small lantern". How are you feeling about that today?"
**LLM Response:** "Your grounding phrase is "steady river, small lantern." It’s such a calming image—how has that phrase been feeling for you lately?"
**LLM Time:** 1658.96ms
**Policy Adherence:** PASS
- PASS: expected content found (2/5 key phrases)
**Pipeline Elapsed:** 1689.85ms
- PASS mode: expected `direct_answer`, got `None`
- PASS mention: expected `True`, got `None`
- PASS detail: expected `exact_value`, got `exact_value`

---
## Test 9: STRICT: Direct review sentence question → must answer with needle value
**Category:** `direct_review`
**Status:** PASS PASS
**User Message:** "What exact sentence did I ask you to remember for my performance review?"
**Detected Emotion:** `neutral` (intent: direct_memory_question)
**Preferred Memory Type:** `review_preparation`
**Retrieval Query:** `What exact sentence did I ask you to remember for my performance review?. memory`
**Retrieved:** 1 memories
**Top Memory:** session_003_moment_review_sentence (review_preparation) sim=1.000
**Emotional Plan:** strategy=gentle_follow_up, topic=performance review preparation, exact=I'd like to understand how I can grow fr...
**Policy Decision:** mode=direct_answer, mention=True, detail=exact_value
**Template Response:** "Thanks for sharing that. You asked me to remember this: "I'd like to understand how I can grow from here.". How are you feeling about that today?"
**LLM Response:** "You asked me to remember this sentence for your review: "I'd like to understand how I can grow from here."

It’s a wonderful, proactive way to approach that conversation. How are you feeling about using it?"
**LLM Time:** 1186.98ms
**Policy Adherence:** PASS
- PASS: expected content found (6/6 key phrases)
**Pipeline Elapsed:** 1230.94ms
- PASS mode: expected `direct_answer`, got `None`
- PASS mention: expected `True`, got `None`
- PASS detail: expected `exact_value`, got `exact_value`

---
## Test 10: STRICT: Direct plan question → must answer with needle value
**Category:** `direct_plan`
**Status:** PASS PASS
**User Message:** "What was the small preparation plan I made before the review?"
**Detected Emotion:** `neutral` (intent: direct_memory_question)
**Preferred Memory Type:** `review_preparation`
**Retrieval Query:** `What was the small preparation plan I made before the review?. memory_type: revi`
**Retrieved:** 1 memories
**Top Memory:** session_003_moment_preparation_plan (follow_up_intent) sim=1.000
**Emotional Plan:** strategy=gentle_follow_up, topic=preparation plan, exact=walk for ten minutes, then write three c...
**Policy Decision:** mode=direct_answer, mention=True, detail=exact_value
**Template Response:** "Thanks for sharing that. You asked me to remember this: "walk for ten minutes, then write three calm bullet points before the review". How are you feeling about that today?"
**LLM Response:** "You planned to walk for ten minutes, then write three calm bullet points before your review. 

How are you feeling about that plan as the time approaches?"
**LLM Time:** 3959.31ms
**Policy Adherence:** PASS
- PASS: expected content found (16/23 key phrases)
**Pipeline Elapsed:** 4023.42ms
- PASS mode: expected `direct_answer`, got `None`
- PASS mention: expected `True`, got `None`
- PASS detail: expected `exact_value`, got `exact_value`

---
