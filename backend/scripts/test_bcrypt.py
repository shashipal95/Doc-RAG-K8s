import asyncio
import bcrypt

def test_bcrypt_directly():
    password = "MySecurePassword123"
    
    # How signup hashes it:
    hashed_bytes = bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt())
    hashed_str = hashed_bytes.decode("utf-8")
    
    print(f"Original Password: {password}")
    print(f"Hashed (str): {hashed_str}")
    
    # How login verifies it:
    # 1. verify with original hashed_str
    h_bytes_1 = hashed_str if isinstance(hashed_str, bytes) else hashed_str.encode("utf-8")
    verify_1 = bcrypt.checkpw(password.encode("utf-8"), h_bytes_1)
    print(f"Verify 1 (using h_bytes_1): {verify_1}")
    
    # Let's test with a different encoding or checkpw directly
    verify_direct = bcrypt.checkpw(password.encode("utf-8"), hashed_bytes)
    print(f"Verify Direct (using hashed_bytes): {verify_direct}")

if __name__ == "__main__":
    test_bcrypt_directly()
