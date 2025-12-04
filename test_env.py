
##Test um zu sehen ob der OPENAI_API_KEY und die DATABASE_URL richtig geladen werden 
import os
from dotenv import load_dotenv

load_dotenv()

print("API KEY:", os.getenv("OPENAI_API_KEY"))
print("DB URL:", os.getenv("DATABASE_URL"))
