"""
=============================================================================
AGENT: Customer Discovery Agent & 11-Stage Pipeline Orchestrator (discovery_agent.py)
=============================================================================
Powers the live split-screen experience:
- Ingests text or microphone speech
- Cleans and protects registration IDs (GSTIN & Udyam)
- Performs Indic language detection (Hindi, Telugu, Tamil, Kannada, Malayalam, Bengali, Marathi, English)
- Extracts zero-temperature schema facts via Sarvam 105B
- Automatically enriches City Tier mappings
- Computes visual schema diffs
- Evaluates missing fields and percentage meter
- Plans the next single question with business justification
- Generates responses in the speaker's native Indic language via Sarvam AI
- Synthesizes natural voice audio via Sarvam bulbul:v3 TTS
- Generates the 11-stage pipeline trace returned to the frontend visualizer
=============================================================================
"""

import re
import time
from typing import Dict, Any, Optional

from agent.session_memory import session_memory
from agent.speech_cleaner import SpeechCleaner
from agent.sarvam_llm_client import sarvam_llm_client
from agent.entity_extractor import entity_extractor
from agent.question_planner import QuestionPlanner
from data_preprocessing.city_tier_mapping import city_tier_service


class CustomerDiscoveryAgent:
    def process_turn(
        self,
        message: str = "",
        session_id: Optional[str] = None,
        audio_bytes: Optional[bytes] = None,
        filename: str = "recording.wav",
        mime_type: str = "audio/wav"
    ) -> Dict[str, Any]:
        """
        Executes the full 11-stage AI customer discovery pipeline with native
        multilingual Sarvam AI voice and text processing.
        """
        start_time = time.time()
        session = session_memory.get_or_create(session_id)
        pipeline_trace = []

        stt_transcript = ""
        stt_lang_code = None

        # ---------------------------------------------------------------------
        # STAGE 1 & 2: Customer Speech Input & STT (Sarvam Saaras:v3)
        # ---------------------------------------------------------------------
        if audio_bytes:
            pipeline_trace.append({
                "stage": 1,
                "name": "Customer Speech",
                "status": "SUCCESS",
                "data": {
                    "audio_size_bytes": len(audio_bytes),
                    "filename": filename,
                    "mime_type": mime_type
                }
            })
            # Speech-to-Text via Sarvam Saaras:v3
            stt_result = sarvam_llm_client.speech_to_text(audio_bytes, filename, mime_type)
            raw_text = stt_result.get("transcript", "")
            stt_lang_code = stt_result.get("language_code")
            cleaned_text = SpeechCleaner.clean(raw_text)
            message = cleaned_text or raw_text
            stt_transcript = message

            pipeline_trace.append({
                "stage": 2,
                "name": "Speech-to-Text (Sarvam Saaras:v3)",
                "status": "SUCCESS",
                "data": {
                    "raw_transcript": raw_text,
                    "cleaned_transcript": cleaned_text,
                    "language_code": stt_lang_code
                }
            })
        else:
            cleaned_text = SpeechCleaner.clean(message)
            pipeline_trace.append({
                "stage": 1,
                "name": "Customer Speech",
                "status": "SKIPPED",
                "data": {"mode": "text_input"}
            })
            pipeline_trace.append({
                "stage": 2,
                "name": "Speech-to-Text",
                "status": "SKIPPED",
                "data": {"input": message, "cleaned": cleaned_text}
            })
            message = cleaned_text

        # ---------------------------------------------------------------------
        # STAGE 3: Indic Language Detection
        # ---------------------------------------------------------------------
        LANG_MAP = {
            "hi-IN": ("Hindi", "Devanagari"),
            "te-IN": ("Telugu", "Telugu"),
            "ta-IN": ("Tamil", "Tamil"),
            "kn-IN": ("Kannada", "Kannada"),
            "ml-IN": ("Malayalam", "Malayalam"),
            "bn-IN": ("Bengali", "Bengali"),
            "mr-IN": ("Marathi", "Devanagari"),
            "gu-IN": ("Gujarati", "Gujarati"),
            "pa-IN": ("Punjabi", "Gurmukhi"),
            "en-IN": ("English", "Latin")
        }

        detected_language = "English"
        detected_script = "Latin"
        detected_lang_code = "en-IN"

        if stt_lang_code and stt_lang_code in LANG_MAP:
            detected_language, detected_script = LANG_MAP[stt_lang_code]
            detected_lang_code = stt_lang_code
        else:
            # Script & Keyword regex detection
            if re.search(r'[\u0C00-\u0C7F]', message):
                detected_language, detected_script, detected_lang_code = "Telugu", "Telugu", "te-IN"
            elif re.search(r'[\u0B80-\u0BFF]', message):
                detected_language, detected_script, detected_lang_code = "Tamil", "Tamil", "ta-IN"
            elif re.search(r'[\u0C80-\u0CFF]', message):
                detected_language, detected_script, detected_lang_code = "Kannada", "Kannada", "kn-IN"
            elif re.search(r'[\u0D00-\u0D7F]', message):
                detected_language, detected_script, detected_lang_code = "Malayalam", "Malayalam", "ml-IN"
            elif re.search(r'[\u0980-\u09FF]', message):
                detected_language, detected_script, detected_lang_code = "Bengali", "Bengali", "bn-IN"
            elif re.search(r'[\u0900-\u097F]', message):
                if any(w in message for w in ['आहे', 'नाही', 'कसे', 'पुणे', 'पाहिजे', 'करावा']):
                    detected_language, detected_script, detected_lang_code = "Marathi", "Devanagari", "mr-IN"
                else:
                    detected_language, detected_script, detected_lang_code = "Hindi", "Devanagari", "hi-IN"
            else:
                low = message.lower()
                if any(w in low for w in ["namaste", "aap", "kaise", "hoga", "chahiye", "hai", "bataiye", "dukan", "kripya", "dhanyavaad"]):
                    detected_language, detected_script, detected_lang_code = "Hindi", "Devanagari", "hi-IN"
                elif any(w in low for w in ["namaskaram", "kavali", "undi", "meeru", "cheppandi", "enti", "ekkada", "dhanyavadalu"]):
                    detected_language, detected_script, detected_lang_code = "Telugu", "Telugu", "te-IN"
                elif any(w in low for w in ["vanakkam", "vendum", "enga", "solunga", "irukku", "nandri"]):
                    detected_language, detected_script, detected_lang_code = "Tamil", "Tamil", "ta-IN"
                elif any(w in low for w in ["namaskara", "beku", "ide", "hege", "heli", "dhanyavada"]):
                    detected_language, detected_script, detected_lang_code = "Kannada", "Kannada", "kn-IN"

        pipeline_trace.append({
            "stage": 3,
            "name": "Language Detection",
            "status": "SUCCESS",
            "data": {
                "detected_language": detected_language,
                "language_code": detected_lang_code,
                "script": detected_script
            }
        })

        # ---------------------------------------------------------------------
        # STAGE 4: Schema Extraction (Zero-Temp Sarvam 105B + Conversational Context)
        # ---------------------------------------------------------------------
        last_question = None
        for m in reversed(session.history):
            if m.get("role") in ("assistant", "bot"):
                last_question = m.get("content")
                break

        extracted_facts = entity_extractor.extract(message, last_question=last_question)

        # Automatic City Tier tool lookup if city mentioned
        if "city" in extracted_facts and extracted_facts["city"]:
            tier_info = city_tier_service.lookup(extracted_facts["city"])
            if tier_info.get("matched"):
                extracted_facts["city_tier"] = tier_info.get("city_tier")
                extracted_facts["state"] = tier_info.get("state")

        pipeline_trace.append({
            "stage": 4,
            "name": "Schema Extraction (Sarvam 105B)",
            "status": "SUCCESS",
            "data": {"extracted_entities": extracted_facts}
        })

        # ---------------------------------------------------------------------
        # STAGE 5: Schema Comparison (Diff)
        # ---------------------------------------------------------------------
        old_profile = session.schema.to_dict()
        session.schema = session.schema.merge_updates(extracted_facts)
        new_profile = session.schema.to_dict()

        diff_cards = {}
        for key, val in new_profile.items():
            if old_profile.get(key) != val:
                diff_cards[key] = {
                    "previous": old_profile.get(key),
                    "current": val
                }

        pipeline_trace.append({
            "stage": 5,
            "name": "Schema Comparison (Diff)",
            "status": "SUCCESS",
            "data": {"diff": diff_cards}
        })

        # ---------------------------------------------------------------------
        # STAGE 6: Missing Information Detection
        # ---------------------------------------------------------------------
        detection = QuestionPlanner.detect_missing_fields(session.schema)
        pipeline_trace.append({
            "stage": 6,
            "name": "Missing Information Detection",
            "status": "SUCCESS",
            "data": {
                "missing_fields": detection["missing_fields"],
                "schema_complete": detection["schema_complete"]
            }
        })

        # ---------------------------------------------------------------------
        # STAGE 7: Schema Completion Meter
        # ---------------------------------------------------------------------
        completion_percent = QuestionPlanner.calculate_completion_percentage(session.schema)
        pipeline_trace.append({
            "stage": 7,
            "name": "Schema Completion Meter",
            "status": "SUCCESS",
            "data": {"completion_percentage": completion_percent}
        })

        # ---------------------------------------------------------------------
        # STAGE 8: Deterministic Question Planner
        # ---------------------------------------------------------------------
        plan = QuestionPlanner.plan_next_question(detection["missing_fields"])
        pipeline_trace.append({
            "stage": 8,
            "name": "Question Planner",
            "status": "SUCCESS",
            "data": plan or {"status": "Customer Discovery 100% Completed"}
        })

        # ---------------------------------------------------------------------
        # STAGE 9: Conversation Memory
        # ---------------------------------------------------------------------
        session.add_message("user", message)
        pipeline_trace.append({
            "stage": 9,
            "name": "Conversation Memory",
            "status": "SUCCESS",
            "data": {"turn_count": len(session.history)}
        })

        # ---------------------------------------------------------------------
        # STAGE 10: Current Customer Schema
        # ---------------------------------------------------------------------
        pipeline_trace.append({
            "stage": 10,
            "name": "Current Customer Schema",
            "status": "SUCCESS",
            "data": {"schema": session.schema.to_dict()}
        })

        # ---------------------------------------------------------------------
        # STAGE 11: Ready for Recommendation Status
        # ---------------------------------------------------------------------
        pipeline_trace.append({
            "stage": 11,
            "name": "Ready for Recommendation",
            "status": "SUCCESS",
            "data": {"ready": detection["schema_complete"]}
        })

        # Formulate assistant reply with explicit acknowledgement of captured facts
        captured_summaries = []
        if extracted_facts.get("business_type"):
            captured_summaries.append(f"business as {extracted_facts['business_type']}")
        elif session.schema.business_type and "business_type" in diff_cards:
            captured_summaries.append(f"business as {session.schema.business_type}")

        if extracted_facts.get("city"):
            captured_summaries.append(f"location in {extracted_facts['city']}")
        if extracted_facts.get("employee_count"):
            captured_summaries.append(f"{extracted_facts['employee_count']} employees")
        if extracted_facts.get("num_sites"):
            captured_summaries.append(f"{extracted_facts['num_sites']} site(s)")
        if extracted_facts.get("needs") and len(extracted_facts["needs"]) > 0:
            captured_summaries.append(f"requirements for {', '.join(extracted_facts['needs'])}")
        if extracted_facts.get("monthly_telecom_spend_inr"):
            captured_summaries.append(f"budget around ₹{int(extracted_facts['monthly_telecom_spend_inr'])}/mo")

        ack_prefix = ""
        if captured_summaries:
            ack_prefix = f"Understood, we have noted your {', '.join(captured_summaries)}. "
        elif len(session.history) > 1 and session.schema.business_type:
            ack_prefix = f"Got it, noting this for your {session.schema.business_type} operations. "

        if detection["schema_complete"]:
            b_name = session.schema.business_name or session.schema.business_type or "your business"
            reply = f"{ack_prefix}Thank you! We have verified all requirements for {b_name}. We have customized your enterprise recommendations."
            next_q = "All requirements verified. Please review the customized pricing plan."
        elif plan:
            reply = f"{ack_prefix}{plan['canonical_question']}"
            next_q = plan['canonical_question']
        else:
            reply = f"{ack_prefix}How can Airtel Business further assist your enterprise today?"
            next_q = "How can Airtel Business further assist your enterprise today?"

        # Generate response IN THE SPEAKER'S LANGUAGE using Sarvam AI
        if detected_lang_code != "en-IN" and sarvam_llm_client.api_key:
            try:
                system_prompt = (
                    f"You are the Accel Business (Airtel Business) AI Onboarding Advisor. "
                    f"The customer spoke or wrote in {detected_language} ({detected_lang_code}). "
                    f"Formulate a natural, warm, and concise 1-2 sentence response (strictly under 30 words) "
                    f"in {detected_language} using {detected_script} script that: "
                    f"1. Acknowledges what was captured: '{', '.join(captured_summaries) if captured_summaries else session.schema.business_type or 'your details'}'. "
                    f"2. Asks the customer the next question: '{next_q}'. "
                    f"Do NOT include English translations, markdown headings, or explanation prefixes. "
                    f"Output ONLY the plain {detected_language} message text."
                )
                ai_spoken_reply = sarvam_llm_client.chat_completion(
                    messages=[{"role": "user", "content": system_prompt}],
                    temperature=0.1
                )
                if ai_spoken_reply and len(ai_spoken_reply.strip()) > 3:
                    reply = ai_spoken_reply.strip()
            except Exception as e:
                print(f"Warning: Sarvam multilingual generation fallback: {e}")

        session.add_message("assistant", reply)

        # Synthesize voice audio via Sarvam Bulbul:v3
        audio_b64 = None
        if sarvam_llm_client.api_key:
            try:
                audio_b64 = sarvam_llm_client.text_to_speech(
                    text=reply,
                    target_language_code=detected_lang_code,
                    speaker="kavya"
                )
            except Exception as e:
                print(f"Warning: Sarvam TTS generation error: {e}")

        latency_ms = int((time.time() - start_time) * 1000)

        return {
            "reply": reply,
            "session_id": session.session_id,
            "audio_base64": audio_b64,
            "audio_mime": "audio/wav" if audio_b64 else None,
            "detected_language": detected_language,
            "language_code": detected_lang_code,
            "stt_transcript": stt_transcript if audio_bytes else None,
            "customer_schema": session.schema.to_dict(),
            "missing_fields": detection["missing_fields"],
            "completion_percentage": completion_percent,
            "ready_for_recommendation": detection["schema_complete"],
            "pipeline_trace": pipeline_trace,
            "schema_diff": diff_cards,
            "debug_telemetry": {
                "latency_ms": latency_ms,
                "stt_model": "saaras:v3",
                "llm_model": "sarvam-105b-conversations",
                "tts_model": "bulbul:v3",
                "temperature": 0.0
            }
        }


discovery_agent = CustomerDiscoveryAgent()
