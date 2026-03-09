#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable


IGNORED_DIRS = {
    ".git",
    ".next",
    ".turbo",
    ".vscode",
    ".expo",
    ".idea",
    "dist",
    "build",
    "coverage",
    "node_modules",
}


ENV_FILE_CANDIDATES = [
    ".env",
    ".env.local",
    ".env.development",
    ".env.production",
    ".env.staging",
]


PLACEHOLDER_PATTERNS = [
    re.compile(r"YOUR_[A-Z0-9_]+"),
    re.compile(r"appl_?YOUR", re.IGNORECASE),
    re.compile(r"goog_?YOUR", re.IGNORECASE),
    re.compile(r"sw_[a-z]+_?YOUR", re.IGNORECASE),
    re.compile(r"your[_-]?api[_-]?key", re.IGNORECASE),
    re.compile(r"changeme", re.IGNORECASE),
]


@dataclass
class Finding:
    name: str
    level: str
    ok: bool
    detail: str


def load_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def parse_major_version(version: str | None) -> int | None:
    if not version:
        return None
    match = re.search(r"(\d+)", version)
    return int(match.group(1)) if match else None


def parse_version_tuple(version: str | None) -> tuple[int, ...] | None:
    if not version:
        return None
    parts = re.findall(r"\d+", version)
    return tuple(int(part) for part in parts) if parts else None


def version_gte(version: str | None, minimum: tuple[int, ...]) -> bool:
    parsed = parse_version_tuple(version)
    if not parsed:
        return False
    padded = parsed + (0,) * max(0, len(minimum) - len(parsed))
    return padded[: len(minimum)] >= minimum


def detect_package_manager(root: Path) -> str:
    if (root / "bun.lockb").exists():
        return "bun"
    if (root / "pnpm-lock.yaml").exists():
        return "pnpm"
    if (root / "yarn.lock").exists():
        return "yarn"
    if (root / "package-lock.json").exists():
        return "npm"
    return "unknown"


def find_app_config(root: Path) -> Path | None:
    candidates = [
        "app.json",
        "app.config.json",
        "app.config.js",
        "app.config.ts",
        "app.config.mjs",
        "app.config.cjs",
    ]
    for candidate in candidates:
        path = root / candidate
        if path.exists():
            return path
    return None


def merge_dependency_maps(package_json: dict[str, Any]) -> dict[str, str]:
    merged: dict[str, str] = {}
    for key in ("dependencies", "devDependencies", "peerDependencies"):
        values = package_json.get(key, {})
        if isinstance(values, dict):
            for dep_name, version in values.items():
                merged[str(dep_name)] = str(version)
    return merged


def extract_plugins_from_json_config(config: dict[str, Any]) -> list[Any]:
    expo = config.get("expo", config)
    plugins = expo.get("plugins", [])
    return plugins if isinstance(plugins, list) else []


def summarise_build_properties_from_json(config: dict[str, Any]) -> tuple[str | None, str | None, bool]:
    plugins = extract_plugins_from_json_config(config)
    for plugin in plugins:
        if isinstance(plugin, list) and plugin:
            if plugin[0] == "expo-build-properties" and len(plugin) > 1 and isinstance(plugin[1], dict):
                android = plugin[1].get("android", {})
                ios = plugin[1].get("ios", {})
                min_sdk = android.get("minSdkVersion")
                deployment_target = ios.get("deploymentTarget")
                return (
                    str(min_sdk) if min_sdk is not None else None,
                    str(deployment_target) if deployment_target is not None else None,
                    True,
                )
        elif plugin == "expo-build-properties":
            return (None, None, True)
    return (None, None, False)


def summarise_build_properties_from_text(text: str) -> tuple[str | None, str | None, bool]:
    has_plugin = "expo-build-properties" in text
    min_sdk_match = re.search(r"minSdkVersion\s*[:=]\s*[\"']?(\d+)", text)
    deployment_match = re.search(r"deploymentTarget\s*[:=]\s*[\"']?([0-9.]+)", text)
    return (
        min_sdk_match.group(1) if min_sdk_match else None,
        deployment_match.group(1) if deployment_match else None,
        has_plugin,
    )


def iter_code_files(root: Path) -> Iterable[Path]:
    valid_suffixes = {
        ".ts",
        ".tsx",
        ".js",
        ".jsx",
        ".mjs",
        ".cjs",
        ".json",
        ".xml",
        ".gradle",
        ".kt",
        ".java",
    }
    for path in root.rglob("*"):
        if not path.is_file():
            continue
        if any(part in IGNORED_DIRS for part in path.parts):
            continue
        if path.suffix.lower() not in valid_suffixes:
            continue
        yield path


def search_patterns(root: Path, patterns: dict[str, re.Pattern[str]]) -> dict[str, list[str]]:
    matches: dict[str, list[str]] = {name: [] for name in patterns}
    for file_path in iter_code_files(root):
        try:
            text = file_path.read_text(encoding="utf-8")
        except Exception:
            continue
        relative = str(file_path.relative_to(root))
        for name, pattern in patterns.items():
            if pattern.search(text):
                matches[name].append(relative)
    return matches


def read_text(path: Path) -> str | None:
    try:
        return path.read_text(encoding="utf-8")
    except Exception:
        return None


def find_env_values(root: Path) -> dict[str, str]:
    found: dict[str, str] = {}
    keys = [
        "EXPO_PUBLIC_REVENUECAT_IOS_API_KEY",
        "EXPO_PUBLIC_REVENUECAT_ANDROID_API_KEY",
        "EXPO_PUBLIC_SUPERWALL_IOS_API_KEY",
        "EXPO_PUBLIC_SUPERWALL_ANDROID_API_KEY",
    ]
    for filename in ENV_FILE_CANDIDATES:
        path = root / filename
        if not path.exists():
            continue
        text = read_text(path)
        if not text:
            continue
        for key in keys:
            match = re.search(rf"^{re.escape(key)}\s*=\s*(.+)$", text, flags=re.MULTILINE)
            if match:
                found[key] = match.group(1).strip().strip('\"').strip("'")
    return found


def contains_placeholder(value: str | None) -> bool:
    if not value:
        return False
    return any(pattern.search(value) for pattern in PLACEHOLDER_PATTERNS)


def inspect_android_manifest(root: Path) -> dict[str, Any]:
    manifest_path = root / "android" / "app" / "src" / "main" / "AndroidManifest.xml"
    summary = {
        "path": str(manifest_path.relative_to(root)) if manifest_path.exists() else None,
        "launch_mode": None,
        "billing_permission": False,
        "has_revenuecat_backup_agent": False,
    }
    if not manifest_path.exists():
        return summary

    text = read_text(manifest_path) or ""
    launch_mode_match = re.search(r'android:launchMode="([^"]+)"', text)
    summary["launch_mode"] = launch_mode_match.group(1) if launch_mode_match else None
    summary["billing_permission"] = "com.android.vending.BILLING" in text
    summary["has_revenuecat_backup_agent"] = "RevenueCatBackupAgent" in text
    return summary


def inspect_package_json(root: Path) -> tuple[dict[str, str], str | None]:
    package_json_path = root / "package.json"
    if not package_json_path.exists():
        raise FileNotFoundError("Could not find package.json")
    package_json = load_json(package_json_path)
    dependencies = merge_dependency_maps(package_json)
    return dependencies, dependencies.get("expo")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Validate a React Native Expo repository for a RevenueCat + Superwall integration.",
    )
    parser.add_argument(
        "--project-root",
        default=".",
        help="Path to the Expo project root. Defaults to the current directory.",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Emit machine-readable JSON instead of formatted text.",
    )
    args = parser.parse_args()

    root = Path(args.project_root).resolve()

    try:
        dependencies, expo_version = inspect_package_json(root)
    except Exception as exc:
        print(str(exc), file=sys.stderr)
        return 2

    expo_major = parse_major_version(expo_version)
    package_manager = detect_package_manager(root)
    uses_expo_router = "expo-router" in dependencies or (root / "app").exists()

    app_config_path = find_app_config(root)
    app_config_summary: dict[str, Any] = {
        "path": str(app_config_path.relative_to(root)) if app_config_path else None,
        "has_build_properties": False,
        "android_min_sdk": None,
        "ios_deployment_target": None,
    }

    if app_config_path and app_config_path.suffix == ".json":
        try:
            app_config_json = load_json(app_config_path)
            min_sdk, deployment_target, has_build_properties = summarise_build_properties_from_json(app_config_json)
            app_config_summary.update(
                {
                    "has_build_properties": has_build_properties,
                    "android_min_sdk": min_sdk,
                    "ios_deployment_target": deployment_target,
                }
            )
        except Exception:
            pass
    elif app_config_path:
        text = read_text(app_config_path)
        if text is not None:
            min_sdk, deployment_target, has_plugin = summarise_build_properties_from_text(text)
            app_config_summary.update(
                {
                    "has_build_properties": has_plugin,
                    "android_min_sdk": min_sdk,
                    "ios_deployment_target": deployment_target,
                }
            )

    patterns = {
        "Purchases.configure": re.compile(r"Purchases\.configure\s*\("),
        "purchasesAreCompletedBy": re.compile(r"purchasesAreCompletedBy"),
        "SuperwallProvider": re.compile(r"\bSuperwallProvider\b"),
        "CustomPurchaseControllerProvider": re.compile(r"\bCustomPurchaseControllerProvider\b"),
        "SubscriptionSync": re.compile(r"\bsetSubscriptionStatus\b|\baddCustomerInfoUpdateListener\b"),
        "usePlacement": re.compile(r"\busePlacement\b|\bregisterPlacement\b"),
        "Auth identity sync": re.compile(r"\bPurchases\.logIn\b|\bidentify\s*\("),
        "Observer or sync migration path": re.compile(r"\bsyncPurchases\b|purchasesAreCompletedBy"),
        "Superwall analytics events": re.compile(r"\buseSuperwallEvents\b"),
    }
    pattern_matches = search_patterns(root, patterns)

    env_values = find_env_values(root)
    manifest = inspect_android_manifest(root)

    findings: list[Finding] = [
        Finding(
            name="Expo SDK 53 or newer",
            level="core",
            ok=expo_major is not None and expo_major >= 53,
            detail=f"Detected expo dependency {expo_version!r}",
        ),
        Finding(
            name="expo-superwall installed",
            level="core",
            ok="expo-superwall" in dependencies,
            detail=dependencies.get("expo-superwall", "missing"),
        ),
        Finding(
            name="react-native-purchases installed",
            level="core",
            ok="react-native-purchases" in dependencies,
            detail=dependencies.get("react-native-purchases", "missing"),
        ),
        Finding(
            name="expo-build-properties installed",
            level="core",
            ok="expo-build-properties" in dependencies,
            detail=dependencies.get("expo-build-properties", "missing"),
        ),
        Finding(
            name="App config has expo-build-properties plugin",
            level="config",
            ok=bool(app_config_summary["has_build_properties"]),
            detail=app_config_summary["path"] or "no app config found",
        ),
        Finding(
            name="Android minSdkVersion >= 23",
            level="config",
            ok=(
                app_config_summary["android_min_sdk"] is not None
                and int(str(app_config_summary["android_min_sdk"])) >= 23
            ),
            detail=str(app_config_summary["android_min_sdk"]),
        ),
        Finding(
            name="iOS deploymentTarget >= 15.1",
            level="config",
            ok=version_gte(str(app_config_summary["ios_deployment_target"]), (15, 1)),
            detail=str(app_config_summary["ios_deployment_target"]),
        ),
        Finding(
            name="RevenueCat iOS public key present",
            level="env",
            ok=bool(env_values.get("EXPO_PUBLIC_REVENUECAT_IOS_API_KEY")),
            detail=env_values.get("EXPO_PUBLIC_REVENUECAT_IOS_API_KEY", "missing"),
        ),
        Finding(
            name="RevenueCat Android public key present",
            level="env",
            ok=bool(env_values.get("EXPO_PUBLIC_REVENUECAT_ANDROID_API_KEY")),
            detail=env_values.get("EXPO_PUBLIC_REVENUECAT_ANDROID_API_KEY", "missing"),
        ),
        Finding(
            name="Superwall iOS public key present",
            level="env",
            ok=bool(env_values.get("EXPO_PUBLIC_SUPERWALL_IOS_API_KEY")),
            detail=env_values.get("EXPO_PUBLIC_SUPERWALL_IOS_API_KEY", "missing"),
        ),
        Finding(
            name="Superwall Android public key present",
            level="env",
            ok=bool(env_values.get("EXPO_PUBLIC_SUPERWALL_ANDROID_API_KEY")),
            detail=env_values.get("EXPO_PUBLIC_SUPERWALL_ANDROID_API_KEY", "missing"),
        ),
        Finding(
            name="No obvious placeholder SDK keys in env files",
            level="env",
            ok=all(not contains_placeholder(value) for value in env_values.values()),
            detail=", ".join(sorted(env_values)) if env_values else "no env values found",
        ),
        Finding(
            name="RevenueCat configured in code",
            level="code",
            ok=bool(pattern_matches["Purchases.configure"]),
            detail=", ".join(pattern_matches["Purchases.configure"][:6]) or "not found",
        ),
        Finding(
            name="Superwall provider mounted",
            level="code",
            ok=bool(pattern_matches["SuperwallProvider"]),
            detail=", ".join(pattern_matches["SuperwallProvider"][:6]) or "not found",
        ),
        Finding(
            name="Uses CustomPurchaseControllerProvider or observer-mode migration",
            level="code",
            ok=bool(
                pattern_matches["CustomPurchaseControllerProvider"]
                or pattern_matches["purchasesAreCompletedBy"]
            ),
            detail=", ".join(
                (pattern_matches["CustomPurchaseControllerProvider"][:3] + pattern_matches["purchasesAreCompletedBy"][:3])
            )
            or "not found",
        ),
        Finding(
            name="Subscription status sync present",
            level="code",
            ok=bool(pattern_matches["SubscriptionSync"]),
            detail=", ".join(pattern_matches["SubscriptionSync"][:6]) or "not found",
        ),
        Finding(
            name="Placement registration present",
            level="code",
            ok=bool(pattern_matches["usePlacement"]),
            detail=", ".join(pattern_matches["usePlacement"][:6]) or "not found",
        ),
        Finding(
            name="Identity sync present",
            level="code",
            ok=bool(pattern_matches["Auth identity sync"]),
            detail=", ".join(pattern_matches["Auth identity sync"][:6]) or "not found",
        ),
        Finding(
            name="Android launchMode is standard or singleTop",
            level="android",
            ok=manifest["launch_mode"] in {"standard", "singleTop"} if manifest["path"] else False,
            detail=manifest["launch_mode"] or ("manifest not found" if not manifest["path"] else "not set"),
        ),
        Finding(
            name="Android billing permission declared when native manifest exists",
            level="android",
            ok=manifest["billing_permission"] if manifest["path"] else False,
            detail="present" if manifest["billing_permission"] else ("manifest not found" if not manifest["path"] else "missing"),
        ),
        Finding(
            name="RevenueCat backup agent present when native manifest exists",
            level="android",
            ok=manifest["has_revenuecat_backup_agent"] if manifest["path"] else False,
            detail="present" if manifest["has_revenuecat_backup_agent"] else ("manifest not found" if not manifest["path"] else "missing"),
        ),
    ]

    output = {
        "project_root": str(root),
        "package_manager": package_manager,
        "uses_expo_router": uses_expo_router,
        "expo_version": expo_version,
        "app_config": app_config_summary,
        "android_manifest": manifest,
        "dependencies": {
            "expo-superwall": dependencies.get("expo-superwall"),
            "react-native-purchases": dependencies.get("react-native-purchases"),
            "react-native-purchases-ui": dependencies.get("react-native-purchases-ui"),
            "expo-build-properties": dependencies.get("expo-build-properties"),
        },
        "env_values": env_values,
        "findings": [
            {"name": finding.name, "level": finding.level, "ok": finding.ok, "detail": finding.detail}
            for finding in findings
        ],
        "code_matches": pattern_matches,
    }

    if args.json:
        print(json.dumps(output, indent=2, sort_keys=True))
        core_ok = all(f.ok for f in findings if f.level == "core")
        return 0 if core_ok else 1

    print(f"Project root: {root}")
    print(f"Package manager: {package_manager}")
    print(f"Uses Expo Router: {'yes' if uses_expo_router else 'no'}")
    print(f"Expo dependency: {expo_version or 'missing'}")
    print(f"App config: {app_config_summary['path'] or 'not found'}")
    print()

    current_section = None
    for finding in findings:
        if finding.level != current_section:
            current_section = finding.level
            print(f"{current_section.upper()} CHECKS")
            print("-" * (len(current_section) + 7))
        status = "PASS" if finding.ok else "WARN"
        print(f"[{status}] {finding.name}: {finding.detail}")
        if finding.level != "android":
            continue
    print()

    print("DETECTED CODE MATCHES")
    print("---------------------")
    for label, files in pattern_matches.items():
        if files:
            print(f"[PASS] {label}: {', '.join(files[:8])}")
        else:
            print(f"[WARN] {label}: not found")
    print()

    print("RECOMMENDED NEXT STEPS")
    print("----------------------")
    next_steps: list[str] = []

    if "expo-superwall" not in dependencies or "react-native-purchases" not in dependencies:
        next_steps.append(
            "Install required packages with: npx expo install expo-superwall react-native-purchases expo-build-properties"
        )
    if not app_config_summary["has_build_properties"]:
        next_steps.append(
            "Add the expo-build-properties plugin and set Android minSdkVersion 23 plus iOS deploymentTarget 15.1."
        )
    if not pattern_matches["Purchases.configure"]:
        next_steps.append("Configure RevenueCat once at app startup.")
    if not pattern_matches["SuperwallProvider"]:
        next_steps.append("Wrap the app with SuperwallProvider.")
    if not pattern_matches["CustomPurchaseControllerProvider"] and not pattern_matches["purchasesAreCompletedBy"]:
        next_steps.append(
            "Choose an architecture: add CustomPurchaseControllerProvider, or configure RevenueCat with purchasesAreCompletedBy for a migration path."
        )
    if not pattern_matches["SubscriptionSync"]:
        next_steps.append("Add a RevenueCat-to-Superwall entitlement sync component.")
    if not pattern_matches["Auth identity sync"]:
        next_steps.append("Wire billing identity changes into the existing auth flow.")
    if not pattern_matches["usePlacement"]:
        next_steps.append("Register at least one named Superwall placement from a premium feature entry point.")
    if any(contains_placeholder(value) for value in env_values.values()):
        next_steps.append("Replace placeholder SDK keys in env files with real public keys.")
    if manifest["path"] and manifest["launch_mode"] not in {"standard", "singleTop"}:
        next_steps.append("Set Android launchMode to standard or singleTop.")
    if not manifest["path"]:
        next_steps.append(
            "Managed Expo project detected with no native manifest. Re-check Android launchMode and billing manifest entries after prebuild or EAS build."
        )

    if not next_steps:
        next_steps.append(
            "The repo looks structurally ready. Review dashboard alignment, restore behaviour, identity design, and real-device testing paths."
        )

    for index, step in enumerate(next_steps, start=1):
        print(f"{index}. {step}")

    core_ok = all(f.ok for f in findings if f.level == "core")
    return 0 if core_ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
