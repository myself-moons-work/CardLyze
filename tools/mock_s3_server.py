"""Zero-Dependency Local S3 Mock Server for CardLyze.

Simulates AWS S3 on http://127.0.0.1:4566 without requiring Docker or LocalStack.
Compatible with boto3.client('s3', endpoint_url='http://127.0.0.1:4566').

Usage:
    python tools/mock_s3_server.py
"""

import http.server
import logging
import os
import socketserver
import sys

PORT = 4566
STORAGE_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".s3_mock_storage")

logging.basicConfig(level=logging.INFO, format="%(asctime)s [MOCK-S3] %(message)s")
logger = logging.getLogger("MockS3")


class MockS3Handler(http.server.BaseHTTPRequestHandler):
    """Handles basic S3 REST requests: HEAD, PUT, and GET."""

    def do_HEAD(self):
        # Head bucket or object
        self.send_response(200)
        self.send_header("Content-Type", "application/xml")
        self.end_headers()

    def do_PUT(self):
        # Extract bucket and key from path
        raw_path = self.path.lstrip("/").split("?")[0]
        parts = raw_path.split("/", 1)
        bucket = parts[0]
        key = parts[1] if len(parts) > 1 else ""

        content_length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(content_length)

        if not key:
            # Create bucket request
            bucket_dir = os.path.join(STORAGE_DIR, bucket)
            os.makedirs(bucket_dir, exist_ok=True)
            logger.info("Created S3 bucket: s3://%s", bucket)
            self.send_response(200)
            self.end_headers()
            return

        # Object upload request
        dest_path = os.path.join(STORAGE_DIR, bucket, key.replace("/", os.sep))
        os.makedirs(os.path.dirname(dest_path), exist_ok=True)
        with open(dest_path, "wb") as f:
            f.write(body)

        logger.info("Successfully received: s3://%s/%s (%d bytes)", bucket, key, len(body))
        self.send_response(200)
        self.send_header("ETag", '"mock-s3-etag-ok"')
        self.end_headers()

    def do_GET(self):
        raw_path = self.path.lstrip("/").split("?")[0]
        parts = raw_path.split("/", 1)
        bucket = parts[0]
        key = parts[1] if len(parts) > 1 else ""

        if not key:
            # List bucket root
            self.send_response(200)
            self.send_header("Content-Type", "application/xml")
            self.end_headers()
            self.wfile.write(b"<ListBucketResult></ListBucketResult>")
            return

        target_path = os.path.join(STORAGE_DIR, bucket, key.replace("/", os.sep))
        if os.path.exists(target_path):
            with open(target_path, "rb") as f:
                content = f.read()
            self.send_response(200)
            self.send_header("Content-Length", str(len(content)))
            self.end_headers()
            self.wfile.write(content)
        else:
            self.send_response(404)
            self.end_headers()

    def log_message(self, format, *args):
        # Suppress noisy default HTTP request log
        pass


def main():
    os.makedirs(STORAGE_DIR, exist_ok=True)
    server_address = ("127.0.0.1", PORT)

    class ReusableTCPServer(socketserver.TCPServer):
        allow_reuse_address = True

    try:
        with ReusableTCPServer(server_address, MockS3Handler) as httpd:
            print("=" * 70)
            print(f"CardLyze Zero-Dependency Local S3 Mock Server running on http://127.0.0.1:{PORT}")
            print(f"Uploaded S3 objects stored locally at: {STORAGE_DIR}")
            print("Press CTRL+C to stop.")
            print("=" * 70)
            httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nStopping Mock S3 Server.")
    except Exception as exc:
        print(f"Failed to start server on port {PORT}: {exc}")
        sys.exit(1)


if __name__ == "__main__":
    main()
