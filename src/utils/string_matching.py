"""
String-Matching-Utilities für MP3 Tagger

Funktionen für Fuzzy-String-Matching und Ähnlichkeitsberechnungen.
"""

import re
from typing import List, Tuple, Optional
from fuzzywuzzy import fuzz, process


def normalize_string(text: str) -> str:
    """
    Normalisiert einen String für besseres Matching.
    
    Args:
        text: Zu normalisierender String
        
    Returns:
        Normalisierter String
    """
    if not text:
        return ""
    
    # Zu Lowercase und Whitespace normalisieren
    normalized = text.lower().strip()
    
    # Mehrfache Leerzeichen entfernen
    normalized = re.sub(r'\s+', ' ', normalized)
    
    # Sonderzeichen entfernen (aber Umlaute beibehalten)
    normalized = re.sub(r'[^\w\s\-äöüß]', '', normalized)
    
    # Häufige Abkürzungen expandieren
    replacements = {
        ' feat ': ' featuring ',
        ' ft ': ' featuring ',
        ' vs ': ' versus ',
        ' w/ ': ' with ',
        '&': 'and',
    }
    
    for old, new in replacements.items():
        normalized = normalized.replace(old, new)
    
    return normalized.strip()


def calculate_similarity(str1: str, str2: str) -> float:
    """
    Berechnet die Ähnlichkeit zwischen zwei Strings.
    
    Args:
        str1: Erster String
        str2: Zweiter String
        
    Returns:
        Ähnlichkeitsscore zwischen 0.0 und 1.0
    """
    if not str1 or not str2:
        return 0.0
    
    # Strings normalisieren
    norm1 = normalize_string(str1)
    norm2 = normalize_string(str2)
    
    # Verschiedene Ähnlichkeitsmetriken verwenden
    ratio = fuzz.ratio(norm1, norm2) / 100.0
    partial_ratio = fuzz.partial_ratio(norm1, norm2) / 100.0
    token_sort_ratio = fuzz.token_sort_ratio(norm1, norm2) / 100.0
    token_set_ratio = fuzz.token_set_ratio(norm1, norm2) / 100.0
    
    # Gewichteter Durchschnitt der Metriken
    weighted_score = (
        ratio * 0.3 +
        partial_ratio * 0.2 +
        token_sort_ratio * 0.25 +
        token_set_ratio * 0.25
    )
    
    return min(weighted_score, 1.0)


def find_best_match(query: str, choices: List[str], threshold: float = 0.6) -> Optional[Tuple[str, float]]:
    """
    Findet die beste Übereinstimmung für einen String aus einer Liste von Optionen.
    
    Args:
        query: Suchstring
        choices: Liste von Optionen
        threshold: Mindest-Ähnlichkeitsscore
        
    Returns:
        Tuple aus (beste_übereinstimmung, score) oder None
    """
    if not query or not choices:
        return None
    
    best_match = None
    best_score = 0.0
    
    for choice in choices:
        score = calculate_similarity(query, choice)
        if score > best_score and score >= threshold:
            best_match = choice
            best_score = score
    
    return (best_match, best_score) if best_match else None


def extract_artist_variations(artist: str) -> List[str]:
    """
    Erstellt Variationen eines Künstlernamens für besseres Matching.
    
    Args:
        artist: Ursprünglicher Künstlername
        
    Returns:
        Liste von Künstlernamen-Variationen
    """
    if not artist:
        return []
    
    variations = [artist]
    normalized = normalize_string(artist)
    
    if normalized != artist.lower():
        variations.append(normalized)
    
    # "The" am Anfang entfernen/hinzufügen
    if normalized.startswith('the '):
        variations.append(normalized[4:])
    else:
        variations.append(f'the {normalized}')
    
    # Featuring-Variationen
    if ' featuring ' in normalized:
        main_artist = normalized.split(' featuring ')[0]
        variations.append(main_artist)
    elif ' feat ' in normalized:
        main_artist = normalized.split(' feat ')[0]
        variations.append(main_artist)
    elif ' ft ' in normalized:
        main_artist = normalized.split(' ft ')[0]
        variations.append(main_artist)
    
    return list(set(variations))  # Duplikate entfernen


def extract_title_variations(title: str) -> List[str]:
    """
    Erstellt Variationen eines Songtitels für besseres Matching.
    
    Args:
        title: Ursprünglicher Titel
        
    Returns:
        Liste von Titel-Variationen
    """
    if not title:
        return []
    
    variations = [title]
    normalized = normalize_string(title)
    
    if normalized != title.lower():
        variations.append(normalized)
    
    # Klammern-Inhalte entfernen
    # z.B. "Song (Radio Edit)" -> "Song"
    bracket_pattern = r'\s*\([^)]*\)\s*'
    without_brackets = re.sub(bracket_pattern, ' ', normalized).strip()
    if without_brackets and without_brackets != normalized:
        variations.append(without_brackets)
    
    # Eckige Klammern entfernen
    # z.B. "Song [Official Video]" -> "Song"
    square_pattern = r'\s*\[[^\]]*\]\s*'
    without_squares = re.sub(square_pattern, ' ', normalized).strip()
    if without_squares and without_squares != normalized:
        variations.append(without_squares)
    
    # Version-Bezeichnungen entfernen
    version_patterns = [
        r'\s*(radio\s+edit|extended\s+version|album\s+version|single\s+version).*$',
        r'\s*(remix|mix).*$',
        r'\s*(acoustic|unplugged).*$',
        r'\s*(live|concert).*$',
        r'\s*(official|music\s+video).*$'
    ]
    
    for pattern in version_patterns:
        clean_version = re.sub(pattern, '', normalized, flags=re.IGNORECASE).strip()
        if clean_version and clean_version != normalized:
            variations.append(clean_version)
    
    return list(set(variations))  # Duplikate entfernen


def match_artist_title(
    query_artist: str, 
    query_title: str, 
    candidate_artist: str, 
    candidate_title: str,
    artist_weight: float = 0.6,
    title_weight: float = 0.4
) -> float:
    """
    Berechnet einen kombinierten Ähnlichkeitsscore für Künstler und Titel.
    
    Args:
        query_artist: Gesuchter Künstler
        query_title: Gesuchter Titel
        candidate_artist: Kandidat-Künstler
        candidate_title: Kandidat-Titel
        artist_weight: Gewichtung für Künstler-Ähnlichkeit
        title_weight: Gewichtung für Titel-Ähnlichkeit
        
    Returns:
        Kombinierter Ähnlichkeitsscore zwischen 0.0 und 1.0
    """
    # Künstler-Variationen erstellen und beste Übereinstimmung finden
    artist_variations = extract_artist_variations(query_artist)
    artist_score = 0.0
    
    for variation in artist_variations:
        score = calculate_similarity(variation, candidate_artist)
        artist_score = max(artist_score, score)
    
    # Titel-Variationen erstellen und beste Übereinstimmung finden
    title_variations = extract_title_variations(query_title)
    title_score = 0.0
    
    for variation in title_variations:
        score = calculate_similarity(variation, candidate_title)
        title_score = max(title_score, score)
    
    # Gewichteter kombinierter Score
    combined_score = (artist_score * artist_weight) + (title_score * title_weight)
    
    return min(combined_score, 1.0)


def clean_genre(genre: str) -> str:
    """
    Bereinigt und normalisiert Genre-Strings.
    
    Args:
        genre: Roher Genre-String
        
    Returns:
        Bereinigter Genre-String
    """
    if not genre:
        return ""
    
    # Basis-Bereinigung
    cleaned = genre.strip()
    
    # Häufige Genre-Normalisierungen
    genre_mappings = {
        'hip hop': 'Hip-Hop',
        'hiphop': 'Hip-Hop',
        'hip-hop': 'Hip-Hop',
        'r&b': 'R&B',
        'rnb': 'R&B',
        'r and b': 'R&B',
        'electronic': 'Electronic',
        'techno': 'Electronic',
        'house': 'Electronic',
        'dance': 'Electronic',
        'edm': 'Electronic',
        'pop': 'Pop',
        'rock': 'Rock',
        'alternative': 'Alternative',
        'indie': 'Indie',
        'jazz': 'Jazz',
        'blues': 'Blues',
        'country': 'Country',
        'folk': 'Folk',
        'classical': 'Classical',
        'metal': 'Metal',
        'punk': 'Punk',
        'reggae': 'Reggae',
    }
    
    cleaned_lower = cleaned.lower()
    for key, value in genre_mappings.items():
        if key in cleaned_lower:
            return value
    
    # Titel-Case anwenden
    return cleaned.title()


def extract_year_from_string(text: str) -> Optional[int]:
    """
    Extrahiert ein Jahr aus einem String.
    
    Args:
        text: Text der ein Jahr enthalten könnte
        
    Returns:
        Extrahiertes Jahr oder None
    """
    if not text:
        return None
    
    # Suche nach 4-stelligen Zahlen zwischen 1900 und 2030
    year_pattern = r'\b(19[0-9]{2}|20[0-2][0-9]|2030)\b'
    matches = re.findall(year_pattern, text)
    
    if matches:
        # Nehme das erste gefundene Jahr
        return int(matches[0])
    
    return None


def extract_artist_title_from_filename(filename: str) -> Optional[Tuple[str, str]]:
    """
    Extrahiert Künstler und Titel aus einem Dateinamen.
    
    Args:
        filename: Dateiname (ohne Pfad)
        
    Returns:
        Tuple von (artist, title) oder None wenn nicht erkannt
    """
    # Entferne Dateiendung
    name = filename.replace('.mp3', '').replace('.MP3', '')
    
    # Häufige Trennzeichen für Künstler - Titel
    separators = [' - ', ' – ', ' — ', '_-_', ' | ']
    
    for sep in separators:
        if sep in name:
            parts = name.split(sep, 1)  # Nur beim ersten Vorkommen teilen
            if len(parts) == 2:
                artist = parts[0].strip()
                title = parts[1].strip()
                
                # Minimale Validierung
                if len(artist) > 0 and len(title) > 0:
                    return (artist, title)
    
    # Fallback: Versuche andere Muster
    # Format: "Artist_Title" oder "Artist Title"
    words = name.replace('_', ' ').split()
    if len(words) >= 2:
        # Nimm erstes Wort als Artist, Rest als Title
        artist = words[0]
        title = ' '.join(words[1:])
        return (artist, title)
    
    return None
