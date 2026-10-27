"""
ماژول استقرار و فعال‌سازی خودکار در گیت‌هاب از طریق GitHub REST API
بدون نیاز به نصب git.exe یا ابزارهای جانبی.
"""

import base64
import os
import sys
import time
import requests

GITHUB_API_BASE = "https://api.github.com"


class GitHubAutoDeployer:
    def __init__(self, token, repo_name="bale-telegram-viewer", is_private=False):
        self.token = token.strip()
        self.repo_name = repo_name.strip()
        self.is_private = is_private
        self.headers = {
            "Authorization": f"Bearer {self.token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28"
        }
        self.owner = None

    def authenticate(self):
        resp = requests.get(f"{GITHUB_API_BASE}/user", headers=self.headers, timeout=15)
        if resp.status_code == 200:
            user_data = resp.json()
            self.owner = user_data["login"]
            print(f"✅ احراز هویت موفق با کاربر گیت‌هاب: @{self.owner}")
            return True
        else:
            print(f"❌ خطا در احراز هویت با توکن گیت‌هاب (کد {resp.status_code}): {resp.text}")
            return False

    def create_or_get_repo(self):
        # بررسی وجود مخزن
        check_resp = requests.get(f"{GITHUB_API_BASE}/repos/{self.owner}/{self.repo_name}", headers=self.headers, timeout=15)
        if check_resp.status_code == 200:
            print(f"ℹ️ مخزن '{self.repo_name}' از قبل در حساب شما وجود دارد. بروزرسانی خواهد شد.")
            return True

        # ساخت مخزن جدید
        print(f"[*] در حال ساخت مخزن جدید '{self.repo_name}' به صورت Public...")
        payload = {
            "name": self.repo_name,
            "description": "نمایشگر بدون فیلتر کانال‌های تلگرام در مینی‌اپ بله",
            "private": self.is_private,
            "auto_init": True
        }
        resp = requests.post(f"{GITHUB_API_BASE}/user/repos", headers=self.headers, json=payload, timeout=20)
        if resp.status_code in (200, 201):
            print(f"✅ مخزن با موفقیت ساخته شد: https://github.com/{self.owner}/{self.repo_name}")
            time.sleep(2)  # زمان برای ثبت کامل در گیت‌هاب
            return True
        else:
            print(f"❌ خطا در ساخت مخزن: {resp.status_code} - {resp.text}")
            return False

    def set_workflow_permissions(self):
        """اعطای دسترسی Write به اکشن‌ها جهت پوش روی gh-pages"""
        url = f"{GITHUB_API_BASE}/repos/{self.owner}/{self.repo_name}/actions/permissions/workflow"
        payload = {
            "default_workflow_permissions": "write",
            "can_approve_pull_request_reviews": False
        }
        resp = requests.put(url, headers=self.headers, json=payload, timeout=15)
        if resp.status_code in (200, 204):
            print("✅ دسترسی نوشتن برای GitHub Actions (Read & Write permissions) فعال شد.")
        else:
            print(f"⚠️ اخطار در تنظیم دسترسی اکشن‌ها ({resp.status_code}): {resp.text}")

    def upload_files_to_main(self, root_dir="."):
        """بارگذاری فایل‌های پروژه با استفاده از Git Data API"""
        print("[*] در حال آماده‌سازی و ارسال فایل‌ها به شاخه main...")

        # دریافت SHA آخرین کامیت main
        ref_resp = requests.get(
            f"{GITHUB_API_BASE}/repos/{self.owner}/{self.repo_name}/git/ref/heads/main",
            headers=self.headers,
            timeout=15
        )
        if ref_resp.status_code != 200:
            # اگر شاخه master بود بررسی کنیم
            ref_resp = requests.get(
                f"{GITHUB_API_BASE}/repos/{self.owner}/{self.repo_name}/git/ref/heads/master",
                headers=self.headers,
                timeout=15
            )
            branch = "master"
        else:
            branch = "main"

        latest_commit_sha = ref_resp.json()["object"]["sha"]

        # دریافت base tree
        commit_resp = requests.get(
            f"{GITHUB_API_BASE}/repos/{self.owner}/{self.repo_name}/git/commits/{latest_commit_sha}",
            headers=self.headers,
            timeout=15
        )
        base_tree_sha = commit_resp.json()["tree"]["sha"]

        # فایل‌های مشمول ارسال
        tree_elements = []
        ignore_dirs = {".git", "__pycache__", ".vscode", ".idea", "venv", ".venv"}

        for dirpath, dirnames, filenames in os.walk(root_dir):
            # حذف پوشه‌های نادیده‌گرفته
            dirnames[:] = [d for d in dirnames if d not in ignore_dirs]

            for fname in filenames:
                if fname.endswith((".pyc", ".log", ".tmp")):
                    continue

                full_path = os.path.join(dirpath, fname)
                rel_path = os.path.relpath(full_path, root_dir).replace("\\", "/")

                # خواندن محتوا
                with open(full_path, "rb") as f:
                    content_bytes = f.read()

                # ساخت Blob در گیت‌هاب
                blob_payload = {
                    "content": base64.b64encode(content_bytes).decode("ascii"),
                    "encoding": "base64"
                }
                b_resp = requests.post(
                    f"{GITHUB_API_BASE}/repos/{self.owner}/{self.repo_name}/git/blobs",
                    headers=self.headers,
                    json=blob_payload,
                    timeout=20
                )
                if b_resp.status_code in (200, 201):
                    blob_sha = b_resp.json()["sha"]
                    tree_elements.append({
                        "path": rel_path,
                        "mode": "100644",
                        "type": "blob",
                        "sha": blob_sha
                    })
                else:
                    print(f"⚠️ خطا در آپلود {rel_path}: {b_resp.status_code}")

        print(f"[*] تعداد {len(tree_elements)} فایل آماده کامیت شد. در حال ایجاد Tree...")

        # ساخت Tree
        tree_payload = {
            "base_tree": base_tree_sha,
            "tree": tree_elements
        }
        tree_resp = requests.post(
            f"{GITHUB_API_BASE}/repos/{self.owner}/{self.repo_name}/git/trees",
            headers=self.headers,
            json=tree_payload,
            timeout=25
        )
        new_tree_sha = tree_resp.json()["sha"]

        # ساخت کامیت
        commit_payload = {
            "message": "feat: full setup of bale telegram viewer with actions & miniapp",
            "tree": new_tree_sha,
            "parents": [latest_commit_sha]
        }
        c_resp = requests.post(
            f"{GITHUB_API_BASE}/repos/{self.owner}/{self.repo_name}/git/commits",
            headers=self.headers,
            json=commit_payload,
            timeout=20
        )
        new_commit_sha = c_resp.json()["sha"]

        # بروزرسانی اشاره‌گر شاخه (Ref)
        ref_patch_payload = {
            "sha": new_commit_sha,
            "force": True
        }
        r_resp = requests.patch(
            f"{GITHUB_API_BASE}/repos/{self.owner}/{self.repo_name}/git/refs/heads/{branch}",
            headers=self.headers,
            json=ref_patch_payload,
            timeout=15
        )
        if r_resp.status_code == 200:
            print(f"✅ کامیت با موفقیت به شاخه {branch} ارسال (Push) شد!")
            return True
        else:
            print(f"❌ خطا در بروزرسانی شاخه: {r_resp.text}")
            return False

    def trigger_action_workflow(self):
        """اجرای دستی اکشن جهت ساخت شاخه gh-pages و تولید اولین نسخه داده‌ها"""
        print("[*] در حال اجرای دستی اکشن جمع‌آوری داده‌ها (workflow_dispatch)...")
        url = f"{GITHUB_API_BASE}/repos/{self.owner}/{self.repo_name}/actions/workflows/collector.yml/dispatches"
        payload = {"ref": "main"}
        resp = requests.post(url, headers=self.headers, json=payload, timeout=15)
        if resp.status_code in (200, 204):
            print("✅ پایپ‌لاین GitHub Actions با موفقیت شروع به کار کرد!")
            return True
        else:
            print(f"⚠️ وضعیت شروع اکشن: {resp.status_code} - {resp.text}")
            return False

    def enable_github_pages(self):
        """فعال‌سازی GitHub Pages روی شاخه gh-pages"""
        url = f"{GITHUB_API_BASE}/repos/{self.owner}/{self.repo_name}/pages"
        payload = {
            "source": {
                "branch": "gh-pages",
                "path": "/"
            }
        }
        print("[*] در حال تلاش برای فعال‌سازی GitHub Pages روی شاخه gh-pages...")
        resp = requests.post(url, headers=self.headers, json=payload, timeout=15)
        if resp.status_code in (200, 201):
            pages_info = resp.json()
            site_url = pages_info.get("html_url") or f"https://{self.owner}.github.io/{self.repo_name}/"
            print(f"✅ GitHub Pages فعال شد! آدرس مینی‌اپ شما:\n👉 {site_url}")
            return site_url
        elif resp.status_code == 409:
            # از قبل فعال بوده
            site_url = f"https://{self.owner}.github.io/{self.repo_name}/"
            print(f"ℹ️ GitHub Pages از قبل فعال است:\n👉 {site_url}")
            return site_url
        else:
            print(f"ℹ️ شاخه gh-pages پس از اتمام اولین اجرای اکشن ایجاد می‌شود و سپس Pages فعال خواهد شد.")
            site_url = f"https://{self.owner}.github.io/{self.repo_name}/"
            return site_url


def main():
    if len(sys.argv) < 2:
        print("استفاده: python scripts/github_deployer.py <GITHUB_TOKEN> [REPO_NAME]")
        sys.exit(1)

    token = sys.argv[1]
    repo_name = sys.argv[2] if len(sys.argv) > 2 else "bale-telegram-viewer"

    deployer = GitHubAutoDeployer(token=token, repo_name=repo_name)
    if not deployer.authenticate():
        sys.exit(1)

    if not deployer.create_or_get_repo():
        sys.exit(1)

    deployer.set_workflow_permissions()
    deployer.upload_files_to_main()
    deployer.trigger_action_workflow()
    site_url = deployer.enable_github_pages()

    print("\n" + "=" * 60)
    print("🎉 ارسال و فعال‌سازی تمام بخش‌ها با موفقیت انجام شد!")
    print(f"📦 آدرس مخزن: https://github.com/{deployer.owner}/{deployer.repo_name}")
    print(f"🌐 آدرس مینی‌اپ: {site_url}")
    print("=" * 60)


if __name__ == "__main__":
    main()
