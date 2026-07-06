"""
LLM Report Generator for Maayan.

Uses an LLM (Groq's free-tier Llama models by default, or OpenAI GPT)
to generate human-readable hydraulic engineering reports explaining
detected leaks. Supports English and French.

The LLM does NOT detect leaks — it EXPLAINS them.

Provider selection (in order of priority):
  1. Groq  (GROQ_API_KEY set)   — free tier, OpenAI-compatible API
  2. OpenAI (OPENAI_API_KEY set) — paid, used if no Groq key present
  3. Rule-based template fallback — used if neither key is configured
     or the live API call fails for any reason.
"""

import os
from typing import Optional, Dict
from loguru import logger

try:
    from openai import OpenAI
    OPENAI_SDK_AVAILABLE = True
except ImportError:
    OPENAI_SDK_AVAILABLE = False
    logger.warning("openai package not available (also required for Groq, which uses an OpenAI-compatible API)")

GROQ_BASE_URL = "https://api.groq.com/openai/v1"
GROQ_DEFAULT_MODEL = "llama-3.3-70b-versatile"
OPENAI_DEFAULT_MODEL = "gpt-4o-mini"


SYSTEM_PROMPT_EN = """You are a senior hydraulic engineer and water network specialist
working for CAMWATER (Cameroon Water Utilities Corporation).

Your role is to analyze water pressure anomaly data detected by the Maayan intelligent
leak detection system and produce a clear, professional technical report for field operators.

Keep the report:
- Concise (150-250 words)
- Professional but readable by non-engineers
- Action-oriented with clear recommendations
- Structured with sections: Summary, Technical Analysis, Risk Assessment, Recommended Actions
- Written in formal English suitable for a utility company report
"""

SYSTEM_PROMPT_FR = """Vous êtes un ingénieur hydraulique senior et spécialiste des réseaux d'eau
travaillant pour la CAMWATER (Cameroun Water Utilities Corporation).

Votre rôle est d'analyser les données d'anomalie de pression d'eau détectées par le système
intelligent de détection de fuites Maayan et de produire un rapport technique clair et
professionnel pour les opérateurs de terrain.

Le rapport doit être:
- Concis (150-250 mots)
- Professionnel mais lisible par des non-ingénieurs  
- Axé sur les actions avec des recommandations claires
- Structuré avec les sections: Résumé, Analyse Technique, Évaluation des Risques, Actions Recommandées
- Rédigé en français formel approprié pour une société d'utilité publique
"""


def generate_fallback_report(data: Dict, language: str = "en") -> str:
    """Generate a structured report without LLM (when API key not available)."""
    location = data.get("location", "Unknown")
    probability = data.get("probability", 0)
    severity = data.get("severity", "none").upper()
    pressure_drop = data.get("pressure_drop", 0)
    flow_loss = data.get("estimated_flow_loss", 0)
    confidence = data.get("confidence", 0)
    timestamp = data.get("timestamp", "N/A")

    if language == "fr":
        if not data.get("detected", False):
            return """## Rapport de Système - Maayan CAMWATER

**Statut:** ✅ Réseau Normal

**Résumé:** Aucune anomalie de pression détectée. Le réseau de distribution d'eau
fonctionne dans les paramètres normaux. Toutes les jonctions présentent des pressions
conformes aux valeurs de référence établies.

**Analyse Technique:** Les pressions mesurées aux 12 nœuds de surveillance sont stables.
Aucune déviation statistiquement significative n'a été identifiée.

**Évaluation des Risques:** Risque actuel: FAIBLE. Aucune intervention requise.

**Actions Recommandées:**
- Continuer la surveillance standard
- Maintenir les cycles d'inspection préventive
- Vérifier les lectures des capteurs selon le calendrier de maintenance"""

        return f"""## Rapport de Fuite - Maayan CAMWATER
**Horodatage:** {timestamp}

**⚠️ ALERTE DE FUITE DÉTECTÉE**

**Résumé:**
Une anomalie de pression significative a été détectée dans la zone {location}.
L'analyse combinée statistique et par apprentissage automatique indique une probabilité
de fuite de **{probability:.0f}%** avec un niveau de sévérité **{severity}**.

**Analyse Technique:**
- Localisation: {location}
- Chute de pression mesurée: {pressure_drop:.2f} bar
- Débit de perte estimé: {flow_loss:.1f} L/s
- Niveau de confiance IA: {confidence:.0f}%

**Évaluation des Risques:**
Sévérité: **{severity}** — Cette anomalie requiert une attention {'immédiate' if severity in ['HIGH', 'BURST'] else 'rapide'}.
Un débit non comptabilisé de {flow_loss:.1f} L/s représente une perte hydraulique significative.

**Actions Recommandées:**
1. Dépêcher une équipe terrain vers {location} immédiatement
2. Fermer les vannes d'isolement de ce secteur si nécessaire
3. Inspecter visuellement les regards et surfaces pour signes d'infiltration
4. Documenter les relevés de pression sur site
5. Notifier le superviseur de réseau et mettre à jour le journal CAMWATER"""

    else:
        if not data.get("detected", False):
            return """## System Report - Maayan CAMWATER

**Status:** ✅ Network Normal

**Summary:** No pressure anomalies detected. The water distribution network is operating
within normal parameters. All monitored junctions are showing pressures consistent with
established baseline values.

**Technical Analysis:** Pressure readings across all 12 monitoring nodes are stable.
No statistically significant deviations have been identified by either the statistical
or machine learning detection engines.

**Risk Assessment:** Current risk level: LOW. No intervention required.

**Recommended Actions:**
- Continue standard monitoring protocol
- Maintain scheduled preventive inspection cycles
- Verify sensor readings per maintenance calendar"""

        return f"""## Leak Detection Report - Maayan CAMWATER
**Timestamp:** {timestamp}

**⚠️ LEAK ALERT DETECTED**

**Summary:**
A significant pressure anomaly has been detected in the {location} area.
Combined statistical and machine learning analysis indicates a leak probability
of **{probability:.0f}%** with a severity level of **{severity}**.

**Technical Analysis:**
- Location: {location}
- Measured Pressure Drop: {pressure_drop:.2f} bar
- Estimated Flow Loss: {flow_loss:.1f} L/s
- AI Confidence Level: {confidence:.0f}%

**Risk Assessment:**
Severity: **{severity}** — This anomaly requires {'immediate' if severity in ['HIGH', 'BURST'] else 'prompt'} attention.
An unaccounted flow of {flow_loss:.1f} L/s represents a significant hydraulic loss
and potential service disruption risk for downstream consumers.

**Recommended Actions:**
1. Dispatch field team to {location} immediately
2. Close isolation valves for this sector if necessary
3. Visually inspect manholes and surfaces for signs of water ingress
4. Document on-site pressure readings
5. Notify network supervisor and update CAMWATER operations log"""


class LLMReporter:
    """
    LLM-powered hydraulic engineering report generator.
    Falls back to templated reports if no provider is configured or the API call fails.
    """

    def __init__(self):
        self.max_tokens = int(os.getenv("OPENAI_MAX_TOKENS", "1024"))
        self.client = None
        self.provider = None
        self.model = None

        groq_key = os.getenv("GROQ_API_KEY", "")
        openai_key = os.getenv("OPENAI_API_KEY", "")

        if not OPENAI_SDK_AVAILABLE:
            return

        if groq_key and groq_key != "your-groq-api-key-here":
            try:
                self.client = OpenAI(api_key=groq_key, base_url=GROQ_BASE_URL)
                self.provider = "groq"
                self.model = os.getenv("GROQ_MODEL", GROQ_DEFAULT_MODEL)
                logger.info(f"Groq client initialized (model={self.model}, free tier)")
                return
            except Exception as e:
                logger.warning(f"Groq init failed: {e}")

        if openai_key and openai_key != "your-openai-api-key-here":
            try:
                self.client = OpenAI(api_key=openai_key)
                self.provider = "openai"
                self.model = os.getenv("OPENAI_MODEL", OPENAI_DEFAULT_MODEL)
                logger.info(f"OpenAI client initialized (model={self.model})")
            except Exception as e:
                logger.warning(f"OpenAI init failed: {e}")

    def generate_report(
        self,
        leak_data: Dict,
        language: str = "en",
        additional_context: Optional[str] = None,
    ) -> str:
        """
        Generate a human-readable leak report.

        Args:
            leak_data: LeakReport dict from LeakDetectionEngine
            language: 'en' or 'fr'
            additional_context: Extra operator notes

        Returns:
            Formatted markdown report string
        """
        if self.client is None:
            logger.info("Using fallback report generator (no GROQ_API_KEY or OPENAI_API_KEY configured)")
            return generate_fallback_report(leak_data, language)

        try:
            return self._call_llm(leak_data, language, additional_context)
        except Exception as e:
            logger.error(f"{self.provider} call failed: {e}")
            return generate_fallback_report(leak_data, language)

    def _call_llm(self, data: Dict, language: str, context: Optional[str]) -> str:
        """Make the actual LLM API call (Groq or OpenAI — identical request shape)."""
        system_prompt = SYSTEM_PROMPT_FR if language == "fr" else SYSTEM_PROMPT_EN

        detected = data.get("detected", False)
        location = data.get("location", "Unknown")
        probability = data.get("probability", 0)
        severity = data.get("severity", "none")
        pressure_drop = data.get("pressure_drop", 0)
        flow_loss = data.get("estimated_flow_loss", 0)
        confidence = data.get("confidence", 0)
        affected = ", ".join(data.get("affected_nodes", [])) or "None"
        timestamp = data.get("timestamp", "N/A")

        if language == "fr":
            user_prompt = f"""Générez un rapport de fuite d'eau professionnel pour CAMWATER basé sur les données suivantes du système Maayan:

**Données du Système:**
- Horodatage: {timestamp}
- Fuite détectée: {'OUI' if detected else 'NON'}
- Localisation: {location}
- Probabilité de fuite: {probability:.0f}%
- Sévérité: {severity.upper()}
- Chute de pression: {pressure_drop:.2f} bar
- Débit de perte estimé: {flow_loss:.1f} L/s
- Niveau de confiance IA: {confidence:.0f}%
- Nœuds affectés: {affected}
{f'- Notes opérateur: {context}' if context else ''}

Rédigez le rapport en français avec les sections: Résumé, Analyse Technique, Évaluation des Risques, Actions Recommandées."""
        else:
            user_prompt = f"""Generate a professional water leak report for CAMWATER based on the following Maayan system data:

**System Data:**
- Timestamp: {timestamp}
- Leak Detected: {'YES' if detected else 'NO'}
- Location: {location}
- Leak Probability: {probability:.0f}%
- Severity: {severity.upper()}
- Pressure Drop: {pressure_drop:.2f} bar
- Estimated Flow Loss: {flow_loss:.1f} L/s
- AI Confidence: {confidence:.0f}%
- Affected Nodes: {affected}
{f'- Operator Notes: {context}' if context else ''}

Write the report in English with sections: Summary, Technical Analysis, Risk Assessment, Recommended Actions."""

        response = self.client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            max_tokens=self.max_tokens,
            temperature=0.3,
        )

        return response.choices[0].message.content or generate_fallback_report(data, language)
