import re

LOG_FILE = "run.log"  # Remplace par le nom de ton fichier log si besoin

# Regex pour extraire les menus sans screenshot
def extract_no_screenshot_menus(log_path):
    pattern = re.compile(r"Skipping screenshot for (.+?) because no error indicators were found")
    menus = []
    with open(log_path, encoding="utf-8") as f:
        for line in f:
            match = pattern.search(line)
            if match:
                menu = match.group(1).strip()
                menus.append(menu)
    return menus

def main():
    menus = extract_no_screenshot_menus(LOG_FILE)
    print("Menus sans screenshot (pas d'erreur détectée):")
    for menu in menus:
        print(menu)

if __name__ == "__main__":
    main()
