import os
from dotenv import load_dotenv
load_dotenv()

LANGUAGE = "ar"            # "ar" أو "en"
AGE_RANGE = "3-6"
PAGES = 12
SEED_KEYWORDS = ["bedtime story kids", "coloring book animals",
                 "قصص قبل النوم", "learning alphabet kids"]
# خط عربي (نزّل Amiri-Regular.ttf من Google Fonts وضعه هنا)
ARABIC_FONT = "fonts/Amiri-Regular.ttf"
PAGE_SIZE_IN = 8.5          # كتاب مربع 8.5x8.5 إنش
