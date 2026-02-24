# تشغيل السيرفر محلياً
# على ويندوز --reload-exclude "tests/*" يسبب خطأ (توسيع النمط)، لذلك نُشغّل بدونه
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
