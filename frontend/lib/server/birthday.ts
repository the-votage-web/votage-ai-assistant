// Member birthdays are stored without a year in members.birthday (VARCHAR(4)) as "MMDD",
// e.g. "0315" for 15 March. MMDD sorts in calendar order, which keeps
// "upcoming birthdays" queries simple.

const MAX_DAYS = [31, 29, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31];

const MONTH_NAMES = [
  "january",
  "february",
  "march",
  "april",
  "may",
  "june",
  "july",
  "august",
  "september",
  "october",
  "november",
  "december",
];

export function isValidBirthday(day: number, month: number) {
  return (
    Number.isInteger(day) &&
    Number.isInteger(month) &&
    month >= 1 &&
    month <= 12 &&
    day >= 1 &&
    day <= MAX_DAYS[month - 1]
  );
}

export function toStoredBirthday(day: number, month: number) {
  return `${String(month).padStart(2, "0")}${String(day).padStart(2, "0")}`;
}

export function formatStoredBirthday(stored: string) {
  const month = Number(stored.slice(0, 2));
  const day = Number(stored.slice(2, 4));
  if (!isValidBirthday(day, month)) return stored;
  const name = MONTH_NAMES[month - 1];
  return `${day} ${name.charAt(0).toUpperCase()}${name.slice(1)}`;
}

function monthFromName(token: string) {
  const lowered = token.toLowerCase();
  if (lowered.length < 3) return null;
  const index = MONTH_NAMES.findIndex((name) => name.startsWith(lowered.slice(0, 3)));
  return index >= 0 ? index + 1 : null;
}

/**
 * Parse a day + month typed in chat. Accepts "15/03", "15-3", "15.03", "15 03",
 * "15 March", "15th of March", "March 15". Numeric input is read as day first.
 * Returns the stored "MMDD" value, or null if it isn't a valid date.
 */
export function parseBirthdayMessage(message: string) {
  const text = message.trim().toLowerCase().replace(/(\d)(st|nd|rd|th)\b/g, "$1").replace(/\bof\b/g, " ");

  const numeric = text.match(/^(\d{1,2})\s*[/.\-\s]\s*(\d{1,2})$/);
  if (numeric) {
    const day = Number(numeric[1]);
    const month = Number(numeric[2]);
    return isValidBirthday(day, month) ? toStoredBirthday(day, month) : null;
  }

  const dayFirst = text.match(/^(\d{1,2})\s*[-\s,]*\s*([a-z]+)$/);
  if (dayFirst) {
    const day = Number(dayFirst[1]);
    const month = monthFromName(dayFirst[2]);
    return month && isValidBirthday(day, month) ? toStoredBirthday(day, month) : null;
  }

  const monthFirst = text.match(/^([a-z]+)\s*[-\s,]*\s*(\d{1,2})$/);
  if (monthFirst) {
    const month = monthFromName(monthFirst[1]);
    const day = Number(monthFirst[2]);
    return month && isValidBirthday(day, month) ? toStoredBirthday(day, month) : null;
  }

  return null;
}

/**
 * Validate birth_day / birth_month from an API payload.
 * Returns undefined when neither is supplied, the stored "MMDD" value when valid,
 * and throws when only one is supplied or the date is invalid.
 */
export function birthdayFromPayload(dayInput: unknown, monthInput: unknown) {
  const empty = (value: unknown) => value === undefined || value === null || value === "";
  if (empty(dayInput) && empty(monthInput)) {
    return undefined;
  }
  const day = Number(dayInput);
  const month = Number(monthInput);
  if (!isValidBirthday(day, month)) {
    throw new Error("birth_day and birth_month must form a valid day and month");
  }
  return toStoredBirthday(day, month);
}

// The check-in chat UI shows a day/month picker when a reply mentions "birthday"
// together with "day and month" or "DD/MM", so keep that wording.
export function birthdayPrompt() {
  return "🎂 We don't have your birthday yet. Please enter your birthday (day and month), e.g. 15/03.";
}
