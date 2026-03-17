"use client";

import Link from "next/link";
import PhoneInput from "react-phone-input-2";
import "react-phone-input-2/lib/style.css";
import { useRouter } from "next/navigation";
import { FormEvent, useEffect, useMemo, useState } from "react";
import styles from "./register.module.css";

const DEFAULT_CONNECT_OPTIONS = [
  "KABOD CONNECT",
  "NEWNESS CONNECT",
  "UGBOWO CONNECT",
  "FLOURISH CONNECT",
  "GATEKEEPERS CONNECT",
  "KOINONIA CONNECT",
  "EKEHUAN CONNECT",
];
const DEFAULT_SERVICE_OPTIONS = ["sunday_service", "connect", "special_service"];

export default function RegisterPage() {
  const router = useRouter();
  const base = process.env.NEXT_PUBLIC_API_BASE || "";
  const [busy, setBusy] = useState(false);
  const [notice, setNotice] = useState<{ type: "success" | "error"; text: string } | null>(null);
  const [serviceOptions, setServiceOptions] = useState<string[]>(DEFAULT_SERVICE_OPTIONS);
  const [connectOptions, setConnectOptions] = useState<string[]>(DEFAULT_CONNECT_OPTIONS);

  const [firstName, setFirstName] = useState("");
  const [lastName, setLastName] = useState("");
  const [email, setEmail] = useState("");
  const [phoneNumber, setPhoneNumber] = useState("");
  const [gender, setGender] = useState("male");
  const [maritalStatus, setMaritalStatus] = useState("single");
  const [serviceType, setServiceType] = useState("sunday_service");
  const [connectName, setConnectName] = useState(DEFAULT_CONNECT_OPTIONS[0]);

  const showConnect = useMemo(() => serviceType === "connect", [serviceType]);

  useEffect(() => {
    async function loadOptions() {
      try {
        const url = base ? `${base}/api/register/options` : "/api/register/options";
        const res = await fetch(url);
        if (!res.ok) return;
        const data = (await res.json()) as {
          service_types?: string[];
          connect_groups?: string[];
        };
        const nextServiceOptions =
          data.service_types && data.service_types.length > 0 ? data.service_types : DEFAULT_SERVICE_OPTIONS;
        const nextConnectOptions =
          data.connect_groups && data.connect_groups.length > 0 ? data.connect_groups : DEFAULT_CONNECT_OPTIONS;

        setServiceOptions(nextServiceOptions);
        setConnectOptions(nextConnectOptions);
        setServiceType((curr) => (nextServiceOptions.includes(curr) ? curr : nextServiceOptions[0]));
        setConnectName((curr) => (nextConnectOptions.includes(curr) ? curr : nextConnectOptions[0]));
      } catch {
        // Keep defaults when options cannot be loaded.
      }
    }
    void loadOptions();
  }, [base]);

  async function onSubmit(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    setBusy(true);
    setNotice(null);

    try {
      const normalizedPhone = phoneNumber.startsWith("+") ? phoneNumber : `+${phoneNumber}`;
      const payload = {
        first_name: firstName,
        last_name: lastName,
        email,
        phone_number: normalizedPhone,
        gender,
        marital_status: maritalStatus,
        service_type: serviceType,
        connect_name: showConnect ? connectName : null,
      };

      const url = base ? `${base}/api/register` : "/api/register";
      const res = await fetch(url, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });

      if (!res.ok) {
        let message = "Registration failed. Please try again.";
        try {
          const body = (await res.json()) as { detail?: string; message?: string };
          message = body.detail || body.message || message;
        } catch {
          // Ignore JSON parsing errors and keep default message.
        }
        throw new Error(message);
      }

      const data = (await res.json()) as { ok: boolean; message: string };
      setFirstName("");
      setLastName("");
      setEmail("");
      setPhoneNumber("");
      setGender("male");
      setMaritalStatus("single");
      setServiceType("sunday_service");
      setConnectName(connectOptions[0] ?? DEFAULT_CONNECT_OPTIONS[0]);
      setNotice({
        type: "success",
        text: `${data.message} Redirecting...`,
      });
      setTimeout(() => router.push("/"), 1200);
    } catch (err) {
      setNotice({
        type: "error",
        text: err instanceof Error ? err.message : "Registration failed",
      });
    } finally {
      setBusy(false);
    }
  }

  return (
    <main className={styles.page}>
      {notice && (
        <div
          role="alert"
          style={{
            position: "fixed",
            top: 16,
            left: "50%",
            transform: "translateX(-50%)",
            zIndex: 50,
            minWidth: "min(560px, calc(100vw - 24px))",
            maxWidth: "calc(100vw - 24px)",
            borderRadius: 12,
            padding: "12px 14px",
            fontSize: 14,
            fontWeight: 700,
            color: notice.type === "success" ? "#0f5132" : "#842029",
            background: notice.type === "success" ? "#d1e7dd" : "#f8d7da",
            border: notice.type === "success" ? "1px solid #badbcc" : "1px solid #f5c2c7",
            boxShadow: "0 10px 24px rgba(0, 0, 0, 0.14)",
          }}
        >
          {notice.text}
        </div>
      )}
      <div className={styles.wrap}>
        <Link href="/" className={styles.backLink}>
          <span aria-hidden="true">←</span>
          <span>Back to Home</span>
        </Link>

        <header className={styles.hero}>
          <h1 className={styles.title}>Church Registration</h1>
          <p className={styles.subtitle}>
            Fill in your details to register for service. This helps us welcome you properly and plan
            each gathering smoothly.
          </p>
        </header>

        <section className={styles.card}>
          <form onSubmit={onSubmit} className={styles.form}>
            <div className={styles.rowTwo}>
              <label className={styles.field}>
                <span className={styles.label}>First name</span>
                <input
                  required
                  value={firstName}
                  onChange={(e) => setFirstName(e.target.value)}
                  className={styles.control}
                />
              </label>

              <label className={styles.field}>
                <span className={styles.label}>Last name</span>
                <input
                  required
                  value={lastName}
                  onChange={(e) => setLastName(e.target.value)}
                  className={styles.control}
                />
              </label>
            </div>

            <label className={styles.field}>
              <span className={styles.label}>Email</span>
              <input
                required
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder="e.g. you@example.com"
                className={styles.control}
              />
            </label>

            <label className={styles.field}>
              <span className={styles.label}>Phone number</span>
              <PhoneInput
                country="ng"
                value={phoneNumber}
                onChange={(value) => setPhoneNumber(value)}
                inputProps={{ required: true, name: "phone" }}
                placeholder="e.g. +234 801 234 5678"
                containerClass={styles.phoneContainer}
                inputClass={styles.phoneInput}
                buttonClass={styles.phoneButton}
                dropdownClass={styles.phoneDropdown}
              />
            </label>

            <div className={styles.rowTwo}>
              <label className={styles.field}>
                <span className={styles.label}>Gender</span>
                <select
                  value={gender}
                  onChange={(e) => setGender(e.target.value)}
                  className={styles.control}
                >
                  <option value="male">Male</option>
                  <option value="female">Female</option>
                </select>
              </label>

              <label className={styles.field}>
                <span className={styles.label}>Marital status</span>
                <select
                  value={maritalStatus}
                  onChange={(e) => setMaritalStatus(e.target.value)}
                  className={styles.control}
                >
                  <option value="single">Single</option>
                  <option value="married">Married</option>
                  <option value="divorced">Divorced</option>
                  <option value="widowed">Widowed</option>
                </select>
              </label>
            </div>

            <label className={styles.field}>
              <span className={styles.label}>Service type</span>
              <select
                value={serviceType}
                onChange={(e) => setServiceType(e.target.value)}
                className={styles.control}
              >
                {serviceOptions.map((name) => (
                  <option key={name} value={name}>
                    {name}
                  </option>
                ))}
              </select>
            </label>

            {showConnect && (
              <label className={styles.field}>
                <span className={styles.label}>Connect group</span>
                <select
                  value={connectName}
                  onChange={(e) => setConnectName(e.target.value)}
                  className={styles.control}
                >
                  {connectOptions.map((name) => (
                    <option key={name} value={name}>
                      {name}
                    </option>
                  ))}
                </select>
              </label>
            )}

            <button type="submit" disabled={busy} className={styles.submitButton}>
              {busy ? "Submitting..." : "Submit Registration"}
            </button>
          </form>
        </section>
      </div>
    </main>
  );
}
