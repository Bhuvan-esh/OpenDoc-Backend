"""Unit tests for SSRF protection and URL validation."""

import unittest
from app.services.fetch_guard import FetchGuard, SSRFSecurityError


class TestFetchGuard(unittest.TestCase):
    def test_blocks_localhost_and_loopback(self):
        self.assertTrue(FetchGuard.is_ip_blocked("127.0.0.1"))
        self.assertTrue(FetchGuard.is_ip_blocked("127.0.0.2"))
        self.assertTrue(FetchGuard.is_ip_blocked("::1"))

    def test_blocks_private_rfc1918_networks(self):
        self.assertTrue(FetchGuard.is_ip_blocked("10.0.0.1"))
        self.assertTrue(FetchGuard.is_ip_blocked("172.16.0.1"))
        self.assertTrue(FetchGuard.is_ip_blocked("192.168.1.1"))

    def test_blocks_cloud_metadata_service(self):
        self.assertTrue(FetchGuard.is_ip_blocked("169.254.169.254"))
        self.assertTrue(FetchGuard.is_ip_blocked("169.254.1.1"))

    def test_allows_public_ips(self):
        self.assertFalse(FetchGuard.is_ip_blocked("8.8.8.8"))
        self.assertFalse(FetchGuard.is_ip_blocked("1.1.1.1"))
        self.assertFalse(FetchGuard.is_ip_blocked("140.82.121.4"))  # GitHub

    def test_url_validation_rejects_credentials(self):
        with self.assertRaises(SSRFSecurityError):
            FetchGuard.validate_url("https://user:pass@example.com/docs")

    def test_url_validation_rejects_unsupported_schemes(self):
        with self.assertRaises(SSRFSecurityError):
            FetchGuard.validate_url("file:///etc/passwd")
        with self.assertRaises(SSRFSecurityError):
            FetchGuard.validate_url("gopher://127.0.0.1:70")
        with self.assertRaises(SSRFSecurityError):
            FetchGuard.validate_url("ftp://ftp.example.com")

    def test_url_validation_rejects_direct_private_ips(self):
        with self.assertRaises(SSRFSecurityError):
            FetchGuard.validate_url("http://127.0.0.1:8000/api")
        with self.assertRaises(SSRFSecurityError):
            FetchGuard.validate_url("http://169.254.169.254/latest/meta-data")


if __name__ == "__main__":
    unittest.main()
