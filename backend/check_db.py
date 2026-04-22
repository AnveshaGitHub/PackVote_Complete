from database import execute_query


print("Tables:")
tables = execute_query("SHOW TABLES")
print(tables)

print("\nUsers table structure:")
try:
    desc = execute_query("DESCRIBE users")
    print(desc)
except Exception as e:
    print("Error:", e)

print("\nUsers data:")
try:
    users = execute_query("SELECT * FROM users")
    print(users)
except Exception as e:
    print("Error:", e)



print("Members table:")
print(execute_query("DESCRIBE members"))

print("\nGroup Members table:")
print(execute_query("DESCRIBE group_members"))

print("Votes table:")
print(execute_query("DESCRIBE votes"))