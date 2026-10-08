import re
import math
from collections import Counter
from typing import Dict, Any, List, Tuple
import pandas as pd

class AnalysisValidationError(ValueError):
    """Raised when CSV structure or data violates validation rules."""
    pass

LOCUS_PAIR_REGEX = re.compile(r"^Locus(\d+)_A([12])$", re.IGNORECASE)
LOCUS_ANY_ALLELE_REGEX = re.compile(r"^Locus(\d+)_A(\d+)$", re.IGNORECASE)

def is_blank_call(val: Any) -> bool:
    """Determine whether an allele call is missing or blank."""
    if val is None or pd.isna(val):
        return True
    s = str(val).strip()
    return s == "" or s.lower() in ("na", "nan", "null", "none", ".", "-9", "-999")

def sanitize_allele(val: Any) -> str:
    """Treat allele labels consistently as categorical strings, preserving exact label text."""
    s = str(val).strip()
    # Normalize potential float-like strings from unintended numerical reads (e.g. '142.0' -> '142')
    # if it's purely digits followed by .0
    if re.match(r"^\d+\.0$", s):
        s = s[:-2]
    return s

def identify_locus_columns(columns: List[str]) -> List[Tuple[int, str, str]]:
    """
    Identifies and validates diploid locus column pairs.
    Returns sorted list of tuples: (locus_number, col_A1, col_A2).
    Rejects missing partner columns or malformed locus pairs.
    """
    locus_map: Dict[int, Dict[int, str]] = {}

    for col in columns:
        clean_col = str(col).strip()
        m = LOCUS_PAIR_REGEX.match(clean_col)
        if m:
            loc_num = int(m.group(1))
            allele_idx = int(m.group(2))
            if loc_num not in locus_map:
                locus_map[loc_num] = {}
            if allele_idx in locus_map[loc_num]:
                raise AnalysisValidationError(
                    f"Duplicate column found for Locus {loc_num} allele A{allele_idx}: '{col}'."
                )
            locus_map[loc_num][allele_idx] = col
        else:
            # Check if there is an unsupported allele index (e.g., Locus1_A3)
            m_any = LOCUS_ANY_ALLELE_REGEX.match(clean_col)
            if m_any:
                loc_num = int(m_any.group(1))
                allele_idx = int(m_any.group(2))
                if allele_idx not in (1, 2):
                    raise AnalysisValidationError(
                        f"Unsupported locus column '{col}'. EcoGen Diagnostics only supports diploid loci with '_A1' and '_A2' partner columns."
                    )

    if not locus_map:
        raise AnalysisValidationError(
            "No valid locus columns found. Expected columns named like 'Locus1_A1' and 'Locus1_A2'."
        )

    # Validate complete pairs
    sorted_locus_numbers = sorted(locus_map.keys())
    validated_pairs: List[Tuple[int, str, str]] = []

    for loc_num in sorted_locus_numbers:
        partners = locus_map[loc_num]
        if 1 not in partners:
            raise AnalysisValidationError(
                f"Locus {loc_num} is missing required partner column 'Locus{loc_num}_A1' (found '{partners[2]}')."
            )
        if 2 not in partners:
            raise AnalysisValidationError(
                f"Locus {loc_num} is missing required partner column 'Locus{loc_num}_A2' (found '{partners[1]}')."
            )
        validated_pairs.append((loc_num, partners[1], partners[2]))

    return validated_pairs

def analyze_genetic_bottleneck(df: pd.DataFrame) -> Dict[str, Any]:
    """
    Performs diploid population genetics screening analysis on the provided DataFrame.
    
    Calculations:
    - For each locus:
        - Ho: fraction of complete individuals whose two alleles differ.
        - He: 1 - sum(p_i ** 2), where p_i is allele frequency after pooling both allele columns.
    - Global mean Ho and He averaged equally across loci.
    - Global Fis: (He - Ho) / He. If He == 0, Fis is None (displayed as 'N/A').
    
    Classification Order:
    1. If Ho > He: CRITICAL (red) - Possible recent bottleneck screening pattern.
    2. Else if Fis > 0.15: WARNING (yellow) - Heterozygosity deficit / inbreeding / isolation.
    3. Else: STABLE (green) - Equilibrium / stable screening pattern.
    """
    if df is None or not isinstance(df, pd.DataFrame):
        raise AnalysisValidationError("Input data must be a valid pandas DataFrame.")

    if df.empty or len(df) == 0:
        raise AnalysisValidationError("CSV file contains no data rows (empty or header-only).")

    total_samples = len(df)
    locus_pairs = identify_locus_columns(list(df.columns))

    per_locus_results = []
    locus_ho_values = []
    locus_he_values = []

    for loc_num, col_a1, col_a2 in locus_pairs:
        locus_name = f"Locus{loc_num}"
        series_a1 = df[col_a1]
        series_a2 = df[col_a2]

        complete_genotypes: List[Tuple[str, str]] = []
        for v1, v2 in zip(series_a1, series_a2):
            if is_blank_call(v1) or is_blank_call(v2):
                # Omit incomplete genotype calls pairwise for this locus
                continue
            a1 = sanitize_allele(v1)
            a2 = sanitize_allele(v2)
            complete_genotypes.append((a1, a2))

        valid_count = len(complete_genotypes)
        if valid_count == 0:
            raise AnalysisValidationError(
                f"Locus '{locus_name}' has no complete genotype calls across all rows."
            )

        # 1. Observed Heterozygosity (Ho)
        het_count = sum(1 for a1, a2 in complete_genotypes if a1 != a2)
        ho = het_count / valid_count

        # 2. Expected Heterozygosity (He) from pooled allele frequencies
        pooled_alleles = []
        for a1, a2 in complete_genotypes:
            pooled_alleles.append(a1)
            pooled_alleles.append(a2)

        total_alleles = len(pooled_alleles)  # 2 * valid_count
        allele_counts = Counter(pooled_alleles)
        sum_p_sq = sum((count / total_alleles) ** 2 for count in allele_counts.values())
        he = 1.0 - sum_p_sq

        # Safeguard numerical precision bounds [0.0, 1.0]
        ho = max(0.0, min(1.0, float(ho)))
        he = max(0.0, min(1.0, float(he)))

        locus_ho_values.append(ho)
        locus_he_values.append(he)

        per_locus_results.append({
            "locus": locus_name,
            "samples_analyzed": valid_count,
            "missing_count": total_samples - valid_count,
            "ho": round(ho, 4),
            "he": round(he, 4)
        })

    num_loci = len(per_locus_results)
    mean_ho = sum(locus_ho_values) / num_loci
    mean_he = sum(locus_he_values) / num_loci

    # Calculate Fis using global mean Ho and He
    if mean_he == 0.0 or math.isclose(mean_he, 0.0, abs_tol=1e-12):
        fis = None
    else:
        raw_fis = (mean_he - mean_ho) / mean_he
        if math.isnan(raw_fis) or math.isinf(raw_fis):
            fis = None
        else:
            fis = float(raw_fis)

    # Classification logic strictly in required order:
    # 1. If Ho > He: CRITICAL (red)
    # 2. Else if Fis > 0.15: WARNING (yellow)
    # 3. Else: STABLE (green)
    if mean_ho > mean_he:
        status = "CRITICAL"
        color = "red"
        verdict = (
            "Observed heterozygosity exceeds expected heterozygosity (Ho > He). "
            "Under this screening rule, the pattern is consistent with a possible recent population bottleneck. "
            "Note: This heuristic screening pattern alone does not confirm a bottleneck; formal confirmation "
            "requires testing against expected heterozygosity conditioned on allele counts under appropriate "
            "mutation-drift models (e.g., TPM/SMM)."
        )
    elif fis is not None and fis > 0.15:
        status = "WARNING"
        color = "yellow"
        verdict = (
            f"Heterozygosity deficit observed (Fis = {fis:.4f} > 0.15). "
            "This indicates high homozygosity, which is consistent with inbreeding, population substructure "
            "(Wahlund effect), or demographic isolation and habitat fragmentation."
        )
    else:
        status = "STABLE"
        color = "green"
        fis_text = f"Fis = {fis:.4f}" if fis is not None else "Fis = N/A"
        verdict = (
            f"Population genotype proportions align with baseline expectations ({fis_text} <= 0.15, Ho <= He). "
            "This pattern is consistent with genetic equilibrium under this screening rule. "
            "Note: A simple summary threshold cannot definitively prove equilibrium or rule out subtle demographic or conservation concerns."
        )

    disclaimer = (
        "EcoGen Diagnostics provides preliminary screening metrics for conservation genetic workflows. "
        "This heuristic is not a formal or validated bottleneck test. Formal demographic inference requires "
        "evaluation against allele frequency distributions conditioned on sample size and locus mutation models."
    )

    return {
        "status": status,
        "color": color,
        "summary": {
            "sample_count": total_samples,
            "locus_count": num_loci,
            "ho": round(mean_ho, 4),
            "he": round(mean_he, 4),
            "fis": round(fis, 4) if fis is not None else None,
            "fis_display": f"{round(fis, 4):.4f}" if fis is not None else "N/A"
        },
        "verdict": verdict,
        "disclaimer": disclaimer,
        "loci": per_locus_results
    }
