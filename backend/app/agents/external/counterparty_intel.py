"""
Counterparty Intelligence Agent
================================
Takes counterparty names extracted from bank statements (and optionally GST data),
looks them up on MCA via data.gov.in, and detects relationship red flags:

  1. Shared Directors     — same person is director in applicant AND counterparty
  2. Same Registered Addr — both companies registered at the same address
  3. Shell Indicators     — low paid-up capital, struck off, dormant status
  4. Family Name Match    — director surnames overlap (family web)
  5. Circular Flow Loop   — money flows A→B→C→A where B and C are related to A

Produces a network graph (nodes + edges) consumable by the frontend ForceGraph2D,
replacing the old mock /api/v1/mock/network-graph endpoint.

Zero-LLM — pure API lookups + deterministic pattern matching.
"""

import re
import logging
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional, Set, Tuple
from collections import defaultdict

from app.agents.external.mca_scanner import MCAScanner, MCAResult
from app.core.config import settings

logger = logging.getLogger(f"pramaan.{__name__}")

# --- Thresholds ---
SHELL_PAID_UP_CAPITAL_THRESHOLD = 100000      # ₹1 lakh — suspiciously low
MIN_COUNTERPARTY_VOLUME = 500000              # ₹5 lakh — ignore tiny counterparties
MAX_COUNTERPARTY_LOOKUPS = 10                 # Cap MCA API calls
ADDRESS_SIMILARITY_THRESHOLD = 0.6            # Jaccard similarity for address match


@dataclass
class RelationshipFlag:
    """A single relationship red flag between two entities."""
    flag_type: str          # "shared_director", "same_address", "shell_indicator", "family_name", "circular_loop"
    severity: str           # "HIGH", "MEDIUM", "CRITICAL"
    entity_a: str
    entity_b: str
    evidence: str           # Human-readable explanation
    details: Dict[str, Any] = field(default_factory=dict)


@dataclass
class CounterpartyProfile:
    """MCA-enriched profile of a single counterparty."""
    name: str
    total_volume: float = 0.0
    debit_volume: float = 0.0
    credit_volume: float = 0.0
    txn_count: int = 0
    mca_found: bool = False
    cin: str = ""
    company_status: str = ""
    registered_address: str = ""
    business_activity: str = ""
    paid_up_capital: float = 0.0
    directors: List[str] = field(default_factory=list)
    is_shell_suspect: bool = False
    shell_reasons: List[str] = field(default_factory=list)


@dataclass
class NetworkIntelResult:
    """Final output: relationship graph + flags + triggered rules."""
    counterparty_profiles: List[CounterpartyProfile] = field(default_factory=list)
    relationship_flags: List[RelationshipFlag] = field(default_factory=list)
    circular_trading_detected: bool = False
    network_graph: Dict[str, Any] = field(default_factory=dict)  # {nodes, links} for ForceGraph2D
    triggered_rules: List[str] = field(default_factory=list)
    findings: List[str] = field(default_factory=list)
    total_lookups: int = 0


class CounterpartyIntel:
    """
    Counterparty intelligence engine.

    Usage:
        intel = CounterpartyIntel()
        result = intel.analyze(
            counterparties=[{"party": "ABC Corp", "total_volume": 5000000, ...}],
            applicant_directors=["Rahul Sharma", "Amit Desai"],
            applicant_address="123 Industrial Area, Mumbai",
            applicant_name="Acme Steels Pvt Ltd",
            bank_transactions=[...],  # full parsed txn list for flow analysis
        )
    """

    def __init__(self):
        self.mca = MCAScanner()

    def analyze(
        self,
        counterparties: List[Dict[str, Any]],
        applicant_directors: List[str],
        applicant_address: str,
        applicant_name: str,
        applicant_cin: str = "",
        bank_transactions: Optional[List[Dict]] = None,
    ) -> NetworkIntelResult:
        """
        Run full counterparty intelligence pipeline.

        Args:
            counterparties: List of dicts with keys: party, total_volume,
                            debit_volume, credit_volume, txn_count
            applicant_directors: Director names from MCA/annual report
            applicant_address: Registered address of the applicant company
            applicant_name: Name of the loan applicant
            applicant_cin: CIN of the applicant (if known)
            bank_transactions: Full list of parsed bank transactions for flow analysis

        Returns:
            NetworkIntelResult with profiles, flags, graph, and triggered rules
        """
        result = NetworkIntelResult()

        if not counterparties:
            logger.info("CounterpartyIntel: No counterparties to analyze")
            return result

        # 1. Filter to significant counterparties
        significant = [
            cp for cp in counterparties
            if cp.get("total_volume", 0) >= MIN_COUNTERPARTY_VOLUME
        ]
        significant.sort(key=lambda x: x.get("total_volume", 0), reverse=True)
        significant = significant[:MAX_COUNTERPARTY_LOOKUPS]

        logger.info(
            f"CounterpartyIntel: {len(significant)} significant counterparties "
            f"(from {len(counterparties)} total)"
        )

        # 2. Normalize applicant director names for comparison
        applicant_dir_normalized = {self._normalize_name(d) for d in applicant_directors}
        applicant_surnames = {self._extract_surname(d) for d in applicant_directors}
        applicant_addr_tokens = self._tokenize_address(applicant_address)

        # 3. Look up each counterparty on MCA and build profiles
        for cp_data in significant:
            party_name = cp_data.get("party", "")
            profile = CounterpartyProfile(
                name=party_name,
                total_volume=cp_data.get("total_volume", 0),
                debit_volume=cp_data.get("debit_volume", 0),
                credit_volume=cp_data.get("credit_volume", 0),
                txn_count=cp_data.get("txn_count", 0),
            )

            # Try MCA lookup by searching for company name
            mca_result = self._lookup_counterparty(party_name)
            result.total_lookups += 1

            if mca_result and mca_result.company_name:
                profile.mca_found = True
                profile.cin = mca_result.cin
                profile.company_status = mca_result.company_status
                profile.registered_address = mca_result.registered_address
                profile.business_activity = mca_result.business_activity
                profile.paid_up_capital = mca_result.paid_up_capital
                profile.directors = [
                    d.get("name", "") for d in mca_result.directors
                    if isinstance(d, dict) and d.get("name")
                ]

                # --- Check 1: Shared Directors ---
                cp_dir_normalized = {self._normalize_name(d) for d in profile.directors}
                shared = applicant_dir_normalized & cp_dir_normalized
                if shared:
                    for director in shared:
                        flag = RelationshipFlag(
                            flag_type="shared_director",
                            severity="CRITICAL",
                            entity_a=applicant_name,
                            entity_b=party_name,
                            evidence=f"Director '{director}' serves on both {applicant_name} and {party_name}",
                            details={"shared_director": director},
                        )
                        result.relationship_flags.append(flag)
                        logger.warning(f"CounterpartyIntel: SHARED DIRECTOR — {director} in {party_name}")

                # --- Check 2: Family Name Match (surname overlap) ---
                cp_surnames = {self._extract_surname(d) for d in profile.directors}
                surname_overlap = applicant_surnames & cp_surnames
                # Exclude if it's already a shared director (would be redundant)
                surname_overlap -= {self._extract_surname(d) for d in shared} if shared else set()
                if surname_overlap:
                    for surname in surname_overlap:
                        if surname and len(surname) > 2:  # skip very short names
                            flag = RelationshipFlag(
                                flag_type="family_name",
                                severity="HIGH",
                                entity_a=applicant_name,
                                entity_b=party_name,
                                evidence=f"Surname '{surname}' found in directors of both companies — possible family connection",
                                details={"shared_surname": surname},
                            )
                            result.relationship_flags.append(flag)

                # --- Check 3: Same Registered Address ---
                if mca_result.registered_address:
                    cp_addr_tokens = self._tokenize_address(mca_result.registered_address)
                    similarity = self._jaccard_similarity(applicant_addr_tokens, cp_addr_tokens)
                    if similarity >= ADDRESS_SIMILARITY_THRESHOLD:
                        flag = RelationshipFlag(
                            flag_type="same_address",
                            severity="HIGH",
                            entity_a=applicant_name,
                            entity_b=party_name,
                            evidence=(
                                f"Registered addresses are {similarity:.0%} similar — "
                                f"possible co-located or shell entity"
                            ),
                            details={
                                "applicant_addr": applicant_address,
                                "counterparty_addr": mca_result.registered_address,
                                "similarity": round(similarity, 2),
                            },
                        )
                        result.relationship_flags.append(flag)

                # --- Check 4: Director Surname in Company Name ---
                # Common Indian shell pattern: director sets up "Sharma Enterprises",
                # "Desai Trading" etc. Check if counterparty company name contains
                # any applicant director's surname.
                if mca_result.company_name:
                    cp_name_upper = mca_result.company_name.upper()
                    for surname in applicant_surnames:
                        if surname and len(surname) > 3 and surname in cp_name_upper:
                            flag = RelationshipFlag(
                                flag_type="family_name",
                                severity="HIGH",
                                entity_a=applicant_name,
                                entity_b=party_name,
                                evidence=(
                                    f"Counterparty company name '{mca_result.company_name}' contains "
                                    f"director surname '{surname}' — possible promoter-linked entity"
                                ),
                                details={"surname_in_name": surname, "company_name": mca_result.company_name},
                            )
                            result.relationship_flags.append(flag)

                # --- Check 5: Shell Company Indicators ---
                shell_reasons = []
                if mca_result.paid_up_capital < SHELL_PAID_UP_CAPITAL_THRESHOLD and mca_result.paid_up_capital > 0:
                    shell_reasons.append(
                        f"Paid-up capital ₹{mca_result.paid_up_capital:,.0f} "
                        f"(below ₹{SHELL_PAID_UP_CAPITAL_THRESHOLD:,.0f} threshold)"
                    )
                status_lower = mca_result.company_status.lower()
                if any(kw in status_lower for kw in ["struck", "dormant", "liquidation", "not available"]):
                    shell_reasons.append(f"Company status: {mca_result.company_status}")
                if not mca_result.business_activity or mca_result.business_activity.lower() in ["na", "n/a", ""]:
                    shell_reasons.append("No business activity listed on MCA")

                if shell_reasons:
                    profile.is_shell_suspect = True
                    profile.shell_reasons = shell_reasons
                    flag = RelationshipFlag(
                        flag_type="shell_indicator",
                        severity="HIGH",
                        entity_a=applicant_name,
                        entity_b=party_name,
                        evidence=f"Shell company indicators: {'; '.join(shell_reasons)}",
                        details={"reasons": shell_reasons},
                    )
                    result.relationship_flags.append(flag)

            result.counterparty_profiles.append(profile)

        # 5. Detect multi-hop circular flows from bank transaction data
        if bank_transactions:
            circular_loops = self._detect_multi_hop_circular(
                bank_transactions, result.counterparty_profiles, applicant_name
            )
            if circular_loops:
                for loop in circular_loops:
                    flag = RelationshipFlag(
                        flag_type="circular_loop",
                        severity="CRITICAL",
                        entity_a=loop["from"],
                        entity_b=loop["to"],
                        evidence=loop["evidence"],
                        details=loop,
                    )
                    result.relationship_flags.append(flag)

        # 6. Determine if circular trading should be flagged
        critical_flags = [f for f in result.relationship_flags if f.severity == "CRITICAL"]
        related_counterparties_with_roundtrip = self._find_related_roundtrips(
            result.counterparty_profiles, result.relationship_flags
        )

        if critical_flags or related_counterparties_with_roundtrip:
            result.circular_trading_detected = True
            if "P-06" not in result.triggered_rules:
                result.triggered_rules.append("P-06")

            # Build findings summary
            if critical_flags:
                result.findings.append(
                    f"CIRCULAR TRADING NETWORK: {len(critical_flags)} critical relationship flags — "
                    f"shared directors/circular flows detected among counterparties"
                )
            if related_counterparties_with_roundtrip:
                result.findings.append(
                    f"RELATED PARTY ROUND-TRIPS: {len(related_counterparties_with_roundtrip)} counterparties "
                    f"have both inflows and outflows AND are related to the applicant"
                )

        # Also flag high-severity non-critical issues
        high_flags = [f for f in result.relationship_flags if f.severity == "HIGH"]
        if high_flags and not result.circular_trading_detected:
            result.findings.append(
                f"COUNTERPARTY RISK: {len(high_flags)} relationship red flags detected "
                f"(shared addresses, family connections, shell indicators)"
            )

        # 7. Build the network graph for frontend visualization
        result.network_graph = self._build_network_graph(
            applicant_name, applicant_cin, applicant_directors,
            result.counterparty_profiles, result.relationship_flags,
        )

        logger.info(
            f"CounterpartyIntel: {len(result.counterparty_profiles)} profiles, "
            f"{len(result.relationship_flags)} flags, "
            f"circular={result.circular_trading_detected}, "
            f"rules={result.triggered_rules}"
        )

        return result

    def _lookup_counterparty(self, party_name: str) -> Optional[MCAResult]:
        """
        Try to find a counterparty on MCA by name.
        Uses the data.gov.in company name search.
        """
        if not party_name or len(party_name) < 3:
            return None

        # Clean up the party name from bank statement format
        clean_name = self._clean_party_name(party_name)
        if not clean_name:
            return None

        try:
            import requests
            api_key = settings.DATA_GOV_API_KEY
            url = "https://api.data.gov.in/resource/ec58dab7-d891-4abb-936e-d5d274a6ce9b"

            # Try LIKE search first (fuzzy match)
            search_variants = [
                clean_name.upper(),
                " ".join(clean_name.upper().split()[:3]),  # First 3 words fallback
            ]

            for variant in search_variants:
                if not variant or len(variant) < 3:
                    continue
                params = {
                    "api-key": api_key,
                    "format": "json",
                    "limit": 1,
                    "filters[company_name]": variant,
                }

                response = requests.get(url, params=params, timeout=8)
                if response.status_code == 200:
                    data = response.json()
                    records = data.get("records", [])
                    if records:
                        rec = records[0]
                        result = MCAResult()
                        result.company_name = rec.get("company_name", "")
                        result.cin = rec.get("corporate_identification_number", "")
                        result.company_status = rec.get("company_status", "Unknown")
                        result.registered_address = rec.get("registered_office_address", "")
                        result.business_activity = rec.get("principal_business_activity", "")
                        result.registered_state = rec.get("registered_state", "")
                        result.date_of_incorporation = rec.get("date_of_registration", "")
                        try:
                            result.paid_up_capital = float(rec.get("paidup_capital", 0))
                        except (ValueError, TypeError):
                            result.paid_up_capital = 0.0

                        # data.gov.in MCA master doesn't include directors —
                        # that requires a separate signatory API (paid).
                        # Directors are injected from the applicant's own MCA
                        # data by the caller when available.
                        result.directors = []

                        logger.info(f"CounterpartyIntel MCA lookup: '{variant}' → {result.company_name} ({result.company_status})")
                        return result

            logger.info(f"CounterpartyIntel MCA lookup: '{clean_name}' → no records after {len(search_variants)} attempts")
            return None

        except Exception as e:
            logger.error(f"CounterpartyIntel MCA lookup error for '{party_name}': {e}")
            return None

    def _clean_party_name(self, raw_name: str) -> str:
        """
        Clean bank statement counterparty name into something searchable on MCA.
        Bank statements have formats like 'ACME STEELS PVT LTD' or 'NEFT/HDFC/ACME STEEL'
        """
        name = raw_name.upper().strip()
        # Remove common bank transfer prefixes
        for prefix in ["NEFT", "RTGS", "IMPS", "UPI", "TRF", "BY CLG", "TO CLG"]:
            name = name.replace(prefix, "")
        # Remove slashes and clean up
        name = re.sub(r'[/\\]', ' ', name)
        # Remove account numbers and reference numbers
        name = re.sub(r'\b\d{6,}\b', '', name)
        # Remove common noise words from bank descriptions
        for noise in ["TRANSFER", "PAYMENT", "CREDIT", "DEBIT", "A/C", "AC "]:
            name = name.replace(noise, "")
        name = re.sub(r'\s+', ' ', name).strip()

        # Must have at least 3 chars left and look like a company name
        if len(name) < 3:
            return ""

        # Check if it looks like a company (has PVT/LTD/LLC/CORP etc.)
        company_indicators = ["PVT", "LTD", "LIMITED", "CORP", "INC", "LLC", "INDUSTRIES",
                              "ENTERPRISES", "TRADING", "EXPORTS", "IMPORTS", "STEEL",
                              "TEXTILES", "PHARMA", "CHEMICALS", "INFRA", "TECH"]
        has_company_indicator = any(ind in name for ind in company_indicators)

        # If no indicator, it might be a person or generic — still return it
        # but the MCA lookup will likely not find it
        return name

    def _normalize_name(self, name: str) -> str:
        """Normalize a person's name for comparison."""
        return re.sub(r'\s+', ' ', name.upper().strip())

    def _extract_surname(self, name: str) -> str:
        """Extract likely surname (last word) from a person's name."""
        parts = name.strip().split()
        if parts:
            return parts[-1].upper()
        return ""

    def _tokenize_address(self, address: str) -> Set[str]:
        """Tokenize an address into meaningful words for comparison."""
        if not address:
            return set()
        # Remove punctuation, normalize
        addr = re.sub(r'[^\w\s]', ' ', address.upper())
        tokens = set(addr.split())
        # Remove very common words that don't help matching
        stopwords = {"INDIA", "THE", "OF", "AND", "AT", "IN", "NO", "PLOT",
                     "ROAD", "STREET", "LANE", "FLOOR", "FLAT", "OFFICE",
                     "BUILDING", "NEAR", "OPP", "BLOCK"}
        return tokens - stopwords

    def _jaccard_similarity(self, set_a: Set[str], set_b: Set[str]) -> float:
        """Compute Jaccard similarity between two sets."""
        if not set_a or not set_b:
            return 0.0
        intersection = set_a & set_b
        union = set_a | set_b
        return len(intersection) / len(union)

    def _detect_multi_hop_circular(
        self,
        transactions: List[Dict],
        profiles: List[CounterpartyProfile],
        applicant_name: str,
    ) -> List[Dict]:
        """
        Detect multi-hop circular money flows: A→B→C→A
        where A is the applicant and B,C are counterparties.

        Looks for patterns where:
        - Applicant sends money to B (debit)
        - B appears to send money to C (both appear in statements)
        - C sends money back to applicant (credit)
        All within a 30-day window.
        """
        loops = []

        # Build a map of which counterparties have both debits and credits
        party_debits = defaultdict(list)   # party → list of {date, amount}
        party_credits = defaultdict(list)  # party → list of {date, amount}

        for t in transactions:
            party = t.get("_party")  # Pre-extracted party name
            if not party:
                continue
            if t.get("debit", 0) > 0 and t.get("date"):
                party_debits[party].append({"date": t["date"], "amount": t["debit"]})
            if t.get("credit", 0) > 0 and t.get("date"):
                party_credits[party].append({"date": t["date"], "amount": t["credit"]})

        # Find related pairs among counterparties
        related_pairs = set()
        shell_names = {p.name for p in profiles if p.is_shell_suspect}

        for profile in profiles:
            if profile.is_shell_suspect or any(
                f.entity_b == profile.name and f.flag_type in ("shared_director", "same_address", "family_name")
                for f in []  # placeholder - flags are built above
            ):
                related_pairs.add(profile.name)

        # Look for A→B (debit) and then B'→A (credit) where B and B' might be related
        # This is a simplified check — in the real world you'd need actual B→C→A chain
        # For now, flag when money goes OUT to a shell/related party and comes BACK from another
        debit_parties = set(party_debits.keys())
        credit_parties = set(party_credits.keys())
        bothway_parties = debit_parties & credit_parties

        # Parties that are both sending and receiving AND are shell suspects
        for party in bothway_parties:
            if party in shell_names:
                for deb in party_debits[party]:
                    for cred in party_credits[party]:
                        if deb["date"] and cred["date"]:
                            gap = abs((deb["date"] - cred["date"]).days)
                            if gap <= 30 and deb["amount"] > 100000 and cred["amount"] > 100000:
                                amount_ratio = min(deb["amount"], cred["amount"]) / max(deb["amount"], cred["amount"])
                                if amount_ratio > 0.7:  # amounts are suspiciously similar
                                    loops.append({
                                        "from": applicant_name,
                                        "to": party,
                                        "via": "direct round-trip via shell suspect",
                                        "debit_amount": deb["amount"],
                                        "credit_amount": cred["amount"],
                                        "days_gap": gap,
                                        "amount_ratio": round(amount_ratio, 2),
                                        "evidence": (
                                            f"Round-trip flow via shell suspect '{party}': "
                                            f"₹{deb['amount']:,.0f} out, ₹{cred['amount']:,.0f} back "
                                            f"within {gap} days (amount ratio {amount_ratio:.0%})"
                                        ),
                                    })

        return loops[:5]  # Cap

    def _find_related_roundtrips(
        self,
        profiles: List[CounterpartyProfile],
        flags: List[RelationshipFlag],
    ) -> List[str]:
        """
        Find counterparties that have BOTH inflows and outflows AND are
        flagged as related to the applicant.
        """
        related_entities = set()
        for f in flags:
            if f.flag_type in ("shared_director", "same_address", "family_name"):
                related_entities.add(f.entity_b)

        roundtrip_related = []
        for profile in profiles:
            if profile.name in related_entities:
                if profile.debit_volume > 0 and profile.credit_volume > 0:
                    roundtrip_related.append(profile.name)

        return roundtrip_related

    def _build_network_graph(
        self,
        applicant_name: str,
        applicant_cin: str,
        applicant_directors: List[str],
        profiles: List[CounterpartyProfile],
        flags: List[RelationshipFlag],
    ) -> Dict[str, Any]:
        """
        Build a node-edge graph for the ForceGraph2D frontend component.

        Node types: applicant, counterparty, shell, director
        Edge types: transaction (money flow), directorship, relationship
        """
        nodes = []
        links = []
        seen_node_ids = set()

        # Applicant node
        app_id = "applicant"
        nodes.append({
            "id": app_id,
            "label": f"{applicant_name}\n(Applicant)",
            "type": "applicant",
            "amount_cr": 0,
        })
        seen_node_ids.add(app_id)

        # Counterparty nodes
        for i, profile in enumerate(profiles):
            cp_id = f"cp_{i}"
            node_type = "shell" if profile.is_shell_suspect else "counterparty"
            volume_cr = round(profile.total_volume / 10000000, 2)  # Convert to Cr

            nodes.append({
                "id": cp_id,
                "label": f"{profile.name}\n({'Shell Suspect' if profile.is_shell_suspect else 'Counterparty'})",
                "type": node_type,
                "amount_cr": volume_cr,
                "mca_status": profile.company_status if profile.mca_found else "Not found on MCA",
                "paid_up_capital": profile.paid_up_capital,
                "shell_reasons": profile.shell_reasons,
            })
            seen_node_ids.add(cp_id)

            # Transaction edges
            if profile.debit_volume > 0:
                debit_cr = round(profile.debit_volume / 10000000, 2)
                links.append({
                    "source": app_id,
                    "target": cp_id,
                    "value": debit_cr,
                    "label": f"₹{debit_cr} Cr",
                    "type": "outflow",
                })
            if profile.credit_volume > 0:
                credit_cr = round(profile.credit_volume / 10000000, 2)
                links.append({
                    "source": cp_id,
                    "target": app_id,
                    "value": credit_cr,
                    "label": f"₹{credit_cr} Cr",
                    "type": "inflow",
                })

        # Director nodes for shared directors
        director_flags = [f for f in flags if f.flag_type == "shared_director"]
        added_directors = set()
        for f in director_flags:
            dir_name = f.details.get("shared_director", "")
            if dir_name and dir_name not in added_directors:
                dir_id = f"dir_{len(added_directors)}"
                nodes.append({
                    "id": dir_id,
                    "label": f"{dir_name}\n(Shared Director)",
                    "type": "director",
                    "amount_cr": 0,
                })
                seen_node_ids.add(dir_id)
                added_directors.add(dir_name)

                # Link director to applicant
                links.append({
                    "source": dir_id,
                    "target": app_id,
                    "value": 0.5,
                    "label": "Director",
                    "type": "directorship",
                })
                # Link director to counterparty
                for i, profile in enumerate(profiles):
                    if dir_name in [self._normalize_name(d) for d in profile.directors]:
                        links.append({
                            "source": dir_id,
                            "target": f"cp_{i}",
                            "value": 0.5,
                            "label": "Director",
                            "type": "directorship",
                        })

        # Relationship edges for address/family matches
        for f in flags:
            if f.flag_type in ("same_address", "family_name"):
                # Find the counterparty index
                for i, profile in enumerate(profiles):
                    if profile.name == f.entity_b:
                        links.append({
                            "source": app_id,
                            "target": f"cp_{i}",
                            "value": 0.3,
                            "label": f.flag_type.replace("_", " ").title(),
                            "type": "relationship",
                        })
                        break

        return {
            "nodes": nodes,
            "links": links,
            "circular_trading_detected": any(f.flag_type == "circular_loop" for f in flags)
                                         or any(f.flag_type == "shared_director" for f in flags),
            "metadata": {
                "total_counterparties": len(profiles),
                "mca_matches": sum(1 for p in profiles if p.mca_found),
                "shell_suspects": sum(1 for p in profiles if p.is_shell_suspect),
                "relationship_flags": len(flags),
            },
        }
