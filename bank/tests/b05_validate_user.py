from solution import validate_user

n = 0
try:
    n += int(validate_user({"name": "ann", "age": 20}) == [])
except Exception:
    pass
try:
    n += int("name" in validate_user({"name": "", "age": 20}))
except Exception:
    pass
try:
    n += int("age" in validate_user({"name": "ann", "age": 200}))
except Exception:
    pass
try:
    n += int("age" in validate_user({"name": "ann"}))
except Exception:
    pass
try:
    n += int("name" in validate_user({"age": 3}))
except Exception:
    pass
print(f"POINTS {n}/5")
