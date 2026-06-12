JSON_OUTPUT_INSTRUCTION = (
    "Respond ONLY with a JSON object containing exactly two fields: "
    '"reasoning" (a brief string explaining your judgment) and '
    '"score" (a number between 0.0 and 1.0). '
    'Example: {"reasoning": "...", "score": 0.7}'
)

CORRECTIVE_REMINDER = (
    "Your previous response was invalid. Respond ONLY with a JSON object "
    'with exactly two fields: "reasoning" (string) and "score" (a number '
    "between 0.0 and 1.0). Do not include any other text."
)
