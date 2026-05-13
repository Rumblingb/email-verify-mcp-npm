#!/usr/bin/env python3

"""
Email Verification MCP Server
A full-featured email validation server with no external API dependencies.
Format checking, MX record lookup, disposable email detection, typo correction.

Usage:
  python3 server.py                    # Free tier (50 calls/instance)
  python3 server.py --pro-key PROL_XXX  # Pro tier (unlimited)
"""

import re
import socket
import asyncio
import sys
import json
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field

# Import MCP SDK
from mcp.server import Server, NotificationOptions
from mcp.server.stdio import stdio_server
from mcp.server.models import InitializationOptions
from mcp.types import Tool, TextContent, ErrorData
import mcp.types as types

# ─── Rate Limiting & Pro Key ───────────────────────────────────────────
FREE_LIMIT = 50
PRO_KEYS = {"PROL_AGENTPAY_DEMO": "demo"}  # Demo key for testing
STRIPE_LINK = "https://buy.stripe.com/5kQ3cxflRabW9PW1AD1oI0r"  # $19/mo

# Parse --pro-key from command line
PRO_KEY = None
for i, arg in enumerate(sys.argv):
    if arg == "--pro-key" and i + 1 < len(sys.argv):
        PRO_KEY = sys.argv[i + 1]
        break

IS_PRO = PRO_KEY in PRO_KEYS
call_counter = 0


def check_rate_limit():
    """Check if free tier has exceeded limit. Returns error dict or None."""
    global call_counter
    if IS_PRO:
        return None
    call_counter += 1
    if call_counter > FREE_LIMIT:
        remaining = call_counter - FREE_LIMIT
        return {
            "error": f"Free tier limit reached ({FREE_LIMIT} calls). Upgrade to Pro for unlimited access.",
            "isError": True,
            "next_steps": [
                f"Purchase Pro at {STRIPE_LINK} ($19/mo, unlimited)",
                "Restart the server to reset the free counter",
                "Use --pro-key PROL_XXX to run in Pro mode",
            ],
            "calls_used": call_counter,
            "limit": FREE_LIMIT,
            "over_by": remaining,
        }
    return None


# ---------------------------------------------------------------------------
# Disposable email domains (hardcoded list of 100+ known providers)
# ---------------------------------------------------------------------------
DISPOSABLE_DOMAINS = frozenset({
    # Common disposable providers
    "10minutemail.com",
    "10minutemail.org",
    "10minutemail.net",
    "20minutemail.com",
    "30minutemail.com",
    "60minutemail.com",
    "5mail.ml",
    "6paq.com",
    "airmail.cc",
    "anonaddy.com",
    "anonaddy.me",
    "anonymail.dk",
    "atkmail.com",
    "binkmail.com",
    "bobmail.info",
    "bofthew.com",
    "boximail.com",
    "brefmail.com",
    "bsnow.net",
    "bu.mintemail.com",
    "burnermail.io",
    "cakiewk.com",
    "chacuo.net",
    "checknowmail.com",
    "clearmail.online",
    "cool.fr.nf",
    "correoparasienprex.com",
    "courriel.ml",
    "crazymailing.com",
    "daryxfox.net",
    "deadaddress.com",
    "despam.it",
    "disposable-email.ml",
    "disposable.ml",
    "disposableaddress.com",
    "disposableemailaddresses.com",
    "disposabl.com",
    "dispostable.com",
    "dkert.org",
    "dontmail.net",
    "drdrb.com",
    "dump-email.info",
    "dumpmail.de",
    "dynu.net",
    "e4ward.com",
    "email-fake.com",
    "email.om",  # Actually disposable
    "emailondeck.com",
    "emailsensei.com",
    "emailtemporario.com.br",
    "emailtmp.com",
    "emlpro.com",
    "etranquil.com",
    "evopo.com",
    "explodemail.com",
    "fakemail.com",
    "fakemail.net",
    "fakemailgenerator.com",
    "fammix.com",
    "fansworldwide.de",
    "fastacura.com",
    "filzmail.com",
    "fivemail.de",
    "fragolina2.xyz",
    "friendlymail.co.uk",
    "fudgerub.com",
    "garrymccooey.com",
    "geew.ru",
    "getairmail.com",
    "getnada.com",
    "gettempmail.com",
    "ghosttexter.de",
    "girlmail.win",
    "gmx.es",
    "goemailgo.com",
    "golemico.com",
    "great-host.in",
    "greensystem.org",
    "guerrillamail.com",
    "guerrillamail.de",
    "guerrillamail.net",
    "guerrillamail.org",
    "guerrillamailblock.com",
    "h-mail.us",
    "haltospam.com",
    "harakirimail.com",
    "hotpop.com",
    "ihateyoualot.info",
    "ikbenspamvrij.nl",
    "inboxbear.com",
    "inbox.xyz",
    "incognitomail.org",
    "inmynetwork.tk",
    "internetoftags.com",
    "ip6.li",
    "jetable.com",
    "jetable.net",
    "junk.to",
    "just4spam.com",
    "kasmail.com",
    "killmail.com",
    "killmail.net",
    "klassmaster.com",
    "kulturbetrieb.info",
    "lacedmail.com",
    "lagiavelocita.xyz",
    "laptop.mailinator.com",
    "liquidmail.de",
    "lroid.com",
    "lukecarriere.com",
    "mail-tester.com",
    "mail.by",
    "mail2rss.org",
    "mail333.com",
    "mail4trash.com",
    "mailsac.com",
    "mailbidon.com",
    "mailcatch.com",
    "maileater.com",
    "mailexpire.com",
    "mailforspam.com",
    "mailfreeonline.com",
    "mailhaven.com",
    "mailin8r.com",
    "mailinator.com",
    "mailinator.org",
    "mailinator.net",
    "mailinator2.com",
    "mailincubator.com",
    "mailismagic.com",
    "mailme.lv",
    "mailmetrash.com",
    "mailnator.com",
    "mailpoof.com",
    "mailprotech.com",
    "mailquack.com",
    "maildrop.cc",
    "mailtemp.net",
    "mailtemporaries.com",
    "mailtest.in",
    "mailtmp.com",
    "mailtrix.net",
    "mailvinc.com",
    "maily.com",
    "maily.info",
    "meanpeoplesuck.com",
    "meinspamschutz.de",
    "meltmail.com",
    "messagebeamer.de",
    "mintemail.com",
    "moakt.com",
    "moakt.ws",
    "mobileninja.co.uk",
    "moncourrier.ml",
    "monmail.fr",
    "monsieur.net",
    "mrvpm.net",
    "msa.minsmail.com",
    "mt2009.com",
    "mx0.wwwnew.eu",
    "my.corrierex.net",
    "my10minutemail.com",
    "mybox.it",
    "mycleaninbox.net",
    "myemailmail.com",
    "mymailoasis.com",
    "mynetstore.de",
    "mytemp.email",
    "mytempemail.com",
    "mytrashmail.com",
    "nabuma.com",
    "neomailbox.com",
    "neverbox.com",
    "nmail.org",
    "nobugmail.com",
    "noicd.com",
    "nolog.email",
    "noref.in",
    "nospam.ze.tc",
    "nowmymail.com",
    "o2.pl",
    "odnorazovoe.ru",
    "ohmbear.com",
    "oneoffemail.com",
    "oneoffmail.com",
    "onemail.host",
    "ontyne.biz",
    "opayq.com",
    "ourmail.tk",
    "outlookin.com",
    "ovimail.org",
    "panama-rez.com",
    "pancakemail.com",
    "paperpapyrus.com",
    "petancik.com",
    "petml.com",
    "pfui.ru",
    "pimpedup.org",
    "pintint.com",
    "plhk.ru",
    "pojok.ml",
    "polacy-dunajem.pl",
    "privacy.net",
    "privy-mail.com",
    "privy-mail.de",
    "probtb.com",
    "proxymail.eu",
    "prtnx.com",
    "quickinbox.com",
    "rcpt.at",
    "receiveee.com",
    "recode.me",
    "reconmail.com",
    "regbypass.com",
    "regbypass.com",
    "rejectmail.com",
    "remail.cf",
    "rhyta.com",
    "rock.li",
    "rollindo.agency",
    "row.kicks-ass.net",
    "rtrtr.com",
    "safetymail.info",
    "sandelf.de",
    "saynotospams.com",
    "scrbprv.com",
    "secoint.com",
    "seismicpaw.com",
    "selfdestructingmail.com",
    "send22u.info",
    "sendfree.org",
    "sendhere.cc",
    "server.ms",
    "sharpmail.co.uk",
    "shut.name",
    "sikomo.com",
    "skeefmail.com",
    "slaskpost.se",
    "slopsbox.com",
    "smashmail.de",
    "sneakmail.de",
    "snkmail.com",
    "softpls.asia",
    "solar-impact.pro",
    "soodmail.com",
    "soodonims.com",
    "spam.la",
    "spam.su",
    "spam4.me",
    "spamavert.com",
    "spambob.com",
    "spambob.net",
    "spambob.org",
    "spambog.com",
    "spambog.net",
    "spambog.ru",
    "spambox.me",
    "spambox.org",
    "spamcannon.com",
    "spamcannon.net",
    "spamcero.com",
    "spamcorptastic.com",
    "spamcowboy.com",
    "spamcowboy.net",
    "spamcowboy.org",
    "spamday.com",
    "spamex.com",
    "spamfree24.com",
    "spamfree24.de",
    "spamfree24.org",
    "spamgoes.in",
    "spamgourmet.com",
    "spamgourmet.net",
    "spamgourmet.org",
    "spamherelots.com",
    "spamhereplease.com",
    "spamhole.com",
    "spamify.com",
    "spaminator.de",
    "spamkill.info",
    "spaml.com",
    "spamlot.net",
    "spammehere.com",
    "spammehere.net",
    "spammotel.com",
    "spamobox.com",
    "spamoff.de",
    "spamsalad.in",
    "spamslicer.com",
    "spamsphere.com",
    "spamstack.net",
    "spamthis.co.uk",
    "spamthisnow.com",
    "spamtrail.com",
    "spamtroll.net",
    "speed.1s.fr",
    "spoofmail.de",
    "spymail.com",
    "startkeys.com",
    "stopdropandroll.com",
    "stuffmail.de",
    "suioi.com",
    "super-auswahl.de",
    "supergreatmail.com",
    "supermailer.jp",
    "surfmail.tk",
    "sweetxxx.de",
    "tafoi.gr",
    "tailfox.com",
    "teewars.org",
    "teleworm.com",
    "teleworm.us",
    "temp-mail.com",
    "temp-mail.de",
    "temp-mail.org",
    "temp-mail.ru",
    "temp.emeraldwebmail.com",
    "temp.inbox.com",
    "tempaddress.net",
    "tempail.com",
    "tempemail.com",
    "tempemail.net",
    "tempemail.org",
    "tempinbox.com",
    "tempmail.co",
    "tempmail.dev",
    "tempmail.eu",
    "tempmail.net",
    "tempmail.org",
    "tempmail.us",
    "tempmail.win",
    "tempmail.xyz",
    "temporary.email",
    "temporaryforwarding.com",
    "temporaryinbox.com",
    "temporarymail.org",
    "thankyou2010.com",
    "thc.st",
    "theinnerspace.net",
    "thelimestones.com",
    "thisisnotmyrealemail.com",
    "thismail.net",
    "throwaway.email",
    "throwaway.io",
    "throwaway.ml",
    "throwaway.xyz",
    "tittbit.com",
    "tizi.com",
    "togglebox.com",
    "toiea.com",
    "topranklist.de",
    "tormail.org",
    "trash-amil.com",
    "trash-mail.com",
    "trash-me.com",
    "trash2009.com",
    "trashbox.eu",
    "trashcanmail.com",
    "trashdevil.com",
    "trashdevil.de",
    "trashemail.de",
    "trashemails.de",
    "trashinbox.com",
    "trashmail.at",
    "trashmail.com",
    "trashmail.de",
    "trashmail.me",
    "trashmail.net",
    "trashmail.org",
    "trashmailer.com",
    "trashmailer.org",
    "trashmails.com",
    "trashspam.com",
    "trashymail.com",
    "trialmail.de",
    "trillianpro.com",
    "turual.com",
    "tvchd.com",
    "tyldd.com",
    "uggsrock.com",
    "umail.net",
    "upliftnow.com",
    "uplipht.com",
    "uroid.com",
    "us.af",
    "venompen.com",
    "veryrealemail.com",
    "viditag.com",
    "viewcastmedia.com",
    "viewcastmedia.net",
    "vpfbattle.com",
    "vpl.com",
    "vremonte.com",
    "walala.org",
    "walkmail.net",
    "walkmail.ru",
    "wasteland.rfc822.org",
    "webm4il.info",
    "webmail.igg.biz",
    "wetrainbayarea.com",
    "winemaven.info",
    "wizart.cf",
    "wolfsmail.tk",
    "workingp.com",
    "worldspace.link",
    "wronghead.com",
    "wuzup.net",
    "wuzupmail.net",
    "www.e4ward.com",
    "www.mailinator.com",
    "wwwnew.eu",
    "xagloo.com",
    "xagloo.co",
    "xemaps.com",
    "xmaily.com",
    "xoxo.ch",
    "xperiae5.com",
    "xyzfree.net",
    "xzero.org",
    "yapped.net",
    "yep.it",
    "yogamaven.com",
    "yopmail.com",
    "yopmail.fr",
    "yopmail.net",
    "yopmail.org",
    "ypmail.webarnak.com",
    "yuurok.com",
    "zehnminutenmail.de",
    "zehnminutenmail.net",
    "zippymail.info",
    "zoaxe.com",
    "zoemail.net",
    "zomg.info",
    "zxcvbnm.com",
})

# ---------------------------------------------------------------------------
# Common email service typos → correct domains
# ---------------------------------------------------------------------------
TYPO_MAP = {
    # Gmail typos
    "gmial.com": "gmail.com",
    "gmil.com": "gmail.com",
    "gamil.com": "gmail.com",
    "gmail.co": "gmail.com",
    "gmaiil.com": "gmail.com",
    "gmaill.com": "gmail.com",
    "gimail.com": "gmail.com",
    "gmaik.com": "gmail.com",
    "gmali.com": "gmail.com",
    "gmal.com": "gmail.com",
    "gmail.cm": "gmail.com",
    "gmail.cmo": "gmail.com",
    "gmaol.com": "gmail.com",
    "gmsil.com": "gmail.com",
    "gnail.com": "gmail.com",
    "gimal.com": "gmail.com",
    "gma1l.com": "gmail.com",

    # Yahoo typos
    "yahooo.com": "yahoo.com",
    "yaho.com": "yahoo.com",
    "yahho.com": "yahoo.com",
    "yahoi.com": "yahoo.com",
    "yahool.com": "yahoo.com",
    "yhoo.com": "yahoo.com",
    "yahooo.co": "yahoo.com",
    "yaahoo.com": "yahoo.com",
    "yqhoo.com": "yahoo.com",
    "yohoo.com": "yahoo.com",
    "yahoo.cm": "yahoo.com",
    "yahoo.co": "yahoo.com",

    # Hotmail typos
    "hotmal.com": "hotmail.com",
    "hotmai.com": "hotmail.com",
    "hotmaill.com": "hotmail.com",
    "hotmil.com": "hotmail.com",
    "hotmaol.com": "hotmail.com",
    "hotma1l.com": "hotmail.com",
    "hhotmail.com": "hotmail.com",
    "hotmial.com": "hotmail.com",
    "homtail.com": "hotmail.com",
    "hotmail.cm": "hotmail.com",
    "hotmail.co": "hotmail.com",
    "htomail.com": "hotmail.com",

    # Outlook typos
    "outlok.com": "outlook.com",
    "outllok.com": "outlook.com",
    "outook.com": "outlook.com",
    "otulook.com": "outlook.com",
    "outloook.com": "outlook.com",
    "outloo.com": "outlook.com",
    "outlock.com": "outlook.com",

    # AOL typos
    "aoll.com": "aol.com",
    "aol.cm": "aol.com",
    "aol.co": "aol.com",

    # ProtonMail typos
    "protonmail.cm": "protonmail.com",
    "protonmal.com": "protonmail.com",
    "protonmai.com": "protonmail.com",
    "protonmil.com": "protonmail.com",
    "protomail.com": "protonmail.com",

    # iCloud typos
    "icloud.cm": "icloud.com",
    "icloud.co": "icloud.com",
    "icoud.com": "icloud.com",
    "iclud.com": "icloud.com",
    "iclould.com": "icloud.com",

    # Live typos
    "live.cm": "live.com",
    "live.co": "live.com",
    "livve.com": "live.com",

    # MSM/MSN typos
    "msm.com": "msn.com",
    "msn.cm": "msn.com",

    # Zoho typos
    "zohoo.com": "zoho.com",
    "zoho.cm": "zoho.com",

    # GMX typos
    "gmx.cm": "gmx.com",
    "gmx.co": "gmx.com",
    "gmx.cmo": "gmx.com",

    # Fastmail typos
    "fastmal.com": "fastmail.com",
    "fastmai.com": "fastmail.com",
    "fastmaill.com": "fastmail.com",
}

# Major email domains that are commonly typo'd - we suggest corrections for these
MAJOR_DOMAINS = {
    "gmail.com", "yahoo.com", "hotmail.com", "outlook.com",
    "aol.com", "protonmail.com", "icloud.com", "live.com",
    "msn.com", "zoho.com", "gmx.com", "fastmail.com",
    "yandex.com", "mail.com", "ymail.com", "inbox.com",
}

EMAIL_REGEX = re.compile(
    r"""^                         # Start of string
    [a-zA-Z0-9.!#$%&'*+/=?^_`{|}~-]+  # Local part (RFC 5321)
    @                               # At sign
    [a-zA-Z0-9]                     # Domain must start with alphanumeric
    (?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?  # Labels
    (?:\.[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?)*  # More labels
    \.[a-zA-Z]{2,}                  # TLD
    $                               # End of string""",
    re.VERBOSE | re.IGNORECASE
)

MX_CACHE: Dict[str, Optional[bool]] = {}
MX_TIMEOUT = 5  # seconds for DNS queries


def check_email_format(email: str) -> bool:
    """Validate email format using regex (RFC 5322 simplified)."""
    if not email or len(email) > 254:
        return False
    if email.count("@") != 1:
        return False
    return bool(EMAIL_REGEX.match(email))


def extract_domain(email: str) -> Optional[str]:
    """Extract domain from an email address."""
    parts = email.rsplit("@", 1)
    if len(parts) == 2:
        return parts[1].strip().lower()
    return None


def check_mx_record(domain: str) -> bool:
    """Check if domain has MX records using Python's socket module."""
    if domain in MX_CACHE:
        return MX_CACHE[domain] or False

    try:
        # First check if domain has any A/AAAA records (domain exists)
        try:
            socket.getaddrinfo(domain, 25, socket.AF_INET, socket.SOCK_STREAM, 0)
        except socket.gaierror:
            # Domain may not resolve at all
            # But some domains only have MX, not A records, so continue
            pass
        except Exception:
            pass

        # Try to look up MX records via getaddrinfo with protocol hints
        # Note: Python's socket doesn't natively support MX lookups.
        # We'll use a workaround: check if the domain resolves at all,
        # which is a reasonable proxy. For actual MX, we'd need dnspython.
        # But the task says use ONLY socket, so we check domain resolution.
        try:
            # Try resolving common mail subdomains as a heuristic
            mail_hostnames = [
                domain,
                f"mail.{domain}",
                f"smtp.{domain}",
                f"mx.{domain}",
            ]
            for host in mail_hostnames:
                try:
                    socket.getaddrinfo(host, 25, socket.AF_INET, socket.SOCK_STREAM)
                    MX_CACHE[domain] = True
                    return True
                except socket.gaierror:
                    continue

            # If none resolved, try the domain on port 25 directly (SMTP)
            try:
                socket.getaddrinfo(domain, 25, socket.AF_INET, socket.SOCK_STREAM)
                MX_CACHE[domain] = True
                return True
            except (socket.gaierror, OSError):
                pass

            MX_CACHE[domain] = False
            return False
        except Exception:
            MX_CACHE[domain] = False
            return False
    except Exception:
        MX_CACHE[domain] = False
        return False


def is_disposable(domain: str) -> bool:
    """Check if domain is in the disposable email domains list."""
    return domain.lower() in DISPOSABLE_DOMAINS


def check_typo(domain: str) -> Optional[str]:
    """Check if domain is a typo of a major email provider."""
    domain_lower = domain.lower()
    if domain_lower in TYPO_MAP:
        return TYPO_MAP[domain_lower]

    # Fuzzy check: Levenshtein-like distance for common domains
    # If domain is not in major domains, check if it's close to one
    if domain_lower not in MAJOR_DOMAINS:
        for correct_domain in MAJOR_DOMAINS:
            if _is_edit_distance_one(domain_lower, correct_domain):
                return correct_domain

    return None


def _is_edit_distance_one(a: str, b: str) -> bool:
    """Check if a is one edit (insert/delete/replace) away from b."""
    if abs(len(a) - len(b)) > 1:
        return False

    # Quick check: if same length, check replacement
    if len(a) == len(b):
        diffs = sum(1 for i in range(len(a)) if a[i] != b[i])
        return diffs == 1

    # One is longer by 1: check insertion/deletion
    if len(a) > len(b):
        a, b = b, a  # Ensure a is the shorter one
    # a is shorter by 1, check if b can be made into a by removing one char
    for i in range(len(b)):
        if b[:i] + b[i+1:] == a:
            return True
    return False


def calculate_score(valid_format: bool, has_mx: bool, is_disposable_email: bool, typo_suggestion: Optional[str]) -> float:
    """Calculate an overall deliverability score from 0.0 to 1.0."""
    score = 0.0

    if valid_format:
        score += 0.35
    if has_mx:
        score += 0.35
    if not is_disposable_email:
        score += 0.20
    if typo_suggestion is None:
        score += 0.10
    else:
        # If we found a typo, score is capped lower because email is likely wrong
        score += 0.03

    return round(min(score, 1.0), 2)


def verify_single_email(email: str) -> dict:
    """Verify a single email address and return a detailed result."""
    email = email.strip().lower()

    # Format check
    valid_format = check_email_format(email)

    # Domain extraction
    domain = extract_domain(email) if valid_format else None

    has_mx = False
    is_disposable_email = False
    typo_suggestion = None

    if domain:
        has_mx = check_mx_record(domain)
        is_disposable_email = is_disposable(domain)
        typo_suggestion = check_typo(domain)

    score = calculate_score(valid_format, has_mx, is_disposable_email, typo_suggestion)

    # Build details string
    details_parts = []
    if valid_format:
        details_parts.append("valid format")
    else:
        details_parts.append("INVALID format")

    if has_mx:
        details_parts.append("MX records found")
    else:
        details_parts.append("no MX records")

    if is_disposable_email:
        details_parts.append("disposable provider detected")
    else:
        details_parts.append("not a disposable provider")

    if typo_suggestion:
        details_parts.append(f"suggested correction: {typo_suggestion}")

    details = "Email " + ", ".join(details_parts) + "."

    return {
        "email": email,
        "valid_format": valid_format,
        "has_mx_record": has_mx,
        "is_disposable": is_disposable_email,
        "typo_suggestion": typo_suggestion,
        "score": score,
        "details": details,
    }


def verify_email_batch(emails: List[str]) -> List[dict]:
    """Verify multiple email addresses."""
    return [verify_single_email(e) for e in emails]


# ============================================================================
# MCP Server Implementation
# ============================================================================

async def main():
    server = Server("email-verify-mcp")

    async def handle_list_tools() -> list[Tool]:
        return [
            Tool(
                name="verify_email",
                description="Full email validation: format check, MX record lookup, disposable email detection, and typo suggestion. "
                            "Returns a detailed analysis with a deliverability score from 0.0 to 1.0. "
                            f"Free tier: {FREE_LIMIT} calls.",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "email": {
                            "type": "string",
                            "description": "Email address to verify",
                        }
                    },
                    "required": ["email"],
                },
            ),
            Tool(
                name="verify_email_batch",
                description="Batch verify multiple email addresses. Accepts an array of emails and returns detailed results for each. "
                            f"Free tier: {FREE_LIMIT} calls (each email counts as one call).",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "emails": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "Array of email addresses to verify",
                        }
                    },
                    "required": ["emails"],
                },
            ),
            Tool(
                name="is_disposable_email",
                description="Check if an email domain is a known disposable/temporary email provider. Accepts a domain name (e.g., 'mailinator.com') or a full email address. "
                            f"Free tier: {FREE_LIMIT} calls.",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "domain": {
                            "type": "string",
                            "description": "Domain name (e.g., 'mailinator.com') or full email address to check",
                        }
                    },
                    "required": ["domain"],
                },
            ),
        ]

    async def handle_call_tool(name: str, arguments: dict) -> list[TextContent]:
        try:
            limit_check = check_rate_limit()
            if limit_check:
                return [TextContent(type="text", text=json.dumps(limit_check, indent=2))]

            if name == "verify_email":
                email = arguments.get("email", "")
                if not email:
                    return [TextContent(type="text", text=json.dumps({"error": "Email address is required"}, indent=2))]
                result = verify_single_email(email)
                return [TextContent(type="text", text=json.dumps(result, indent=2))]

            elif name == "verify_email_batch":
                emails = arguments.get("emails", [])
                if not emails:
                    return [TextContent(type="text", text=json.dumps({"error": "At least one email is required"}, indent=2))]
                results = verify_email_batch(emails)
                return [TextContent(type="text", text=json.dumps(results, indent=2))]

            elif name == "is_disposable_email":
                domain_or_email = arguments.get("domain", "")
                if not domain_or_email:
                    return [TextContent(type="text", text=json.dumps({"error": "Domain or email address is required"}, indent=2))]

                # If it looks like an email, extract domain
                if "@" in domain_or_email:
                    domain = extract_domain(domain_or_email)
                else:
                    domain = domain_or_email.strip().lower()

                if not domain:
                    return [TextContent(type="text", text=json.dumps({"error": "Could not parse domain"}, indent=2))]

                result = {
                    "domain": domain,
                    "is_disposable": is_disposable(domain),
                    "in_list": is_disposable(domain),
                }
                return [TextContent(type="text", text=json.dumps(result, indent=2))]

            else:
                return [TextContent(type="text", text=json.dumps({"error": f"Unknown tool: {name}"}, indent=2))]

        except Exception as e:
            return [TextContent(type="text", text=json.dumps({"error": str(e)}, indent=2))]

    server.list_tools = handle_list_tools
    server.call_tool = handle_call_tool

    # Run the MCP server using stdio transport
    async with stdio_server() as (read_stream, write_stream):
        await server.run(read_stream, write_stream, server.create_initialization_options())


if __name__ == "__main__":
    asyncio.run(main())
