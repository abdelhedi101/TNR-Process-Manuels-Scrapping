import subprocess, tempfile, os, time

winscp   = r"C:\Program Files (x86)\WinSCP\WinSCP.com"
local    = r"C:\Users\aabdelhedi_ct\Desktop\Megara\TNR_Process_Manuels\Scrapping\SWIFTS\AWB\MT54X\MT54X.txt"
remote   = "/Megara/IODevices/MegaCustody/IN/ALLIANCE/MT54X.txt"
remote_dir = "/Megara/IODevices/MegaCustody/IN/ALLIANCE"
open_cmd = "open sftp://server:server@244@10.1.140.244:22/ -hostkey=* -timeout=30"

def run(script):
    with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False, encoding="utf-8") as f:
        f.write(script)
        p = f.name
    r = subprocess.run([winscp, f"/script={p}"], capture_output=True, text=True, timeout=30)
    os.unlink(p)
    return r

# ── Upload ────────────────────────────────────────────────────────────────────
print("==> Uploading MT54X.swf ...")
r = run(f'{open_cmd}\nput "{local}" "{remote}"\nclose\nexit')
print(f"Upload exit code: {r.returncode}")
if r.returncode != 0:
    print("STDERR:", r.stderr[:400])

# ── Attente 5s puis CTRL+R ────────────────────────────────────────────────────
print("==> Attente 5s ...")
time.sleep(5)
print("==> CTRL+R (ls) ...")
r = run(f"{open_cmd}\nls {remote_dir}/\nclose\nexit")
print(r.stdout[:800])

# ── Poll absorption : CTRL+R toutes les 5s ───────────────────────────────────
print("\n==> Polling (CTRL+R every 5s) ...")
for i in range(30):
    time.sleep(5)
    r = run(f"{open_cmd}\nls {remote_dir}/\nclose\nexit")
    present = "MT54X.txt" in r.stdout
    print(f"  [{(i+1)*5:3d}s] MT54X.txt present={present}")
    if not present:
        print("==> ABSORBED!")
        break
else:
    print("==> TIMEOUT — not absorbed after 150s")
    print(r.stdout[:1000])
