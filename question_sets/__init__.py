# question_sets/__init__.py

from .histoire import QUESTIONS as HISTOIRE_QUESTIONS
from .geographie import QUESTIONS as GEO_QUESTIONS
from .sciences import QUESTIONS as SCIENCES_QUESTIONS
from .technologie import QUESTIONS as TECHNO_QUESTIONS
from .football import QUESTIONS as FOOT_QUESTIONS
from .sport import QUESTIONS as SPORT_QUESTIONS
from .culture_generale import QUESTIONS as CG_QUESTIONS
from .art_musique import QUESTIONS as ART_QUESTIONS

ALL_QUESTIONS = (
    HISTOIRE_QUESTIONS
    + GEO_QUESTIONS
    + SCIENCES_QUESTIONS
    + TECHNO_QUESTIONS
    + FOOT_QUESTIONS
    + SPORT_QUESTIONS
    + CG_QUESTIONS
    + ART_QUESTIONS
)
