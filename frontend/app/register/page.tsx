"use client";

import { Suspense } from "react";
import Link from "next/link";
import PhoneInput from "react-phone-input-2";
import "react-phone-input-2/lib/style.css";
import { useRouter, useSearchParams } from "next/navigation";
import { FormEvent, useEffect, useMemo, useState } from "react";
import styles from "./register.module.css";
import ChatWidget from "@/components/ChatWidget";
import { reportIssue } from "@/lib/reportIssue";

const DEFAULT_CONNECT_OPTIONS = [
  "KABOD",
  "NEWNESS",
  "EKEHUAN",
  "FLOURISH",
  "GATEKEEPERS",
  "KOINONIA",
  "UGBOWO",
];
const DEFAULT_DEPARTMENT_OPTIONS = [
  "RMG",
  "Media",
  "Technical",
  "Ushering",
  "Welfare",
  "VIP",
  "Prayer",
  "Votage_Act",
  "Protocol",
  "Sanitation",
  "Pastorate",
  "Digital_Communication",
  "Others",
];
const DEFAULT_SERVICE_OPTIONS = ["sunday_service", "connect", "special_service"];

function RegisterPageContent() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const base = process.env.NEXT_PUBLIC_API_BASE || "";
  const [activeTab, setActiveTab] = useState<"checkin" | "register">("checkin");
  const [busy, setBusy] = useState(false);
  const [notice, setNotice] = useState<{ type: "success" | "error"; text: string } | null>(null);
  const [serviceOptions, setServiceOptions] = useState<string[]>(DEFAULT_SERVICE_OPTIONS);
  const [connectOptions, setConnectOptions] = useState<string[]>(DEFAULT_CONNECT_OPTIONS);
  const [departmentOptions] = useState<string[]>(DEFAULT_DEPARTMENT_OPTIONS);

  const [firstName, setFirstName] = useState("");
  const [lastName, setLastName] = useState("");
  const [email, setEmail] = useState("");
  const [phoneNumber, setPhoneNumber] = useState("");
  const [gender, setGender] = useState("male");
  const [maritalStatus, setMaritalStatus] = useState("single");
  const [isWorker, setIsWorker] = useState(false);
  const [department, setDepartment] = useState(DEFAULT_DEPARTMENT_OPTIONS[0]);
  const [customDepartment, setCustomDepartment] = useState("");
  const [serviceType, setServiceType] = useState("sunday_service");
  const [connectName, setConnectName] = useState(DEFAULT_CONNECT_OPTIONS[0]);

  const showConnect = useMemo(() => serviceType === "connect", [serviceType]);
  const showDepartment = useMemo(() => showConnect && isWorker, [showConnect, isWorker]);
  const selectedDepartment = useMemo(
    () => (showDepartment ? (department === "Others" ? customDepartment.trim() : department) : null),
    [customDepartment, department, showDepartment],
  );

  useEffect(() => {
    const tab = searchParams.get("tab");
    setActiveTab(tab === "register" || tab === "registration" ? "register" : "checkin");
  }, [searchParams]);

  function switchTab(tab: "checkin" | "register") {
    setActiveTab(tab);
    const params = new URLSearchParams(searchParams.toString());
    if (tab === "register") {
      params.set("tab", "registration");
    } else {
      params.delete("tab");
    }
    const query = params.toString();
    router.replace(query ? `/register?${query}` : "/register");
  }

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

    let httpStatus: number | undefined;
    try {
      const normalizedPhone = phoneNumber.startsWith("+") ? phoneNumber : `+${phoneNumber}`;
      const payload = {
        first_name: firstName,
        last_name: lastName,
        email,
        phone_number: normalizedPhone,
        gender,
        marital_status: maritalStatus,
        is_worker: isWorker,
        department: selectedDepartment,
        service_type: serviceType,
        connect_name: showConnect ? connectName : null,
      };

      const url = base ? `${base}/api/register` : "/api/register";
      const res = await fetch(url, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      httpStatus = res.status;

      if (!res.ok) {
        let message = "Registration failed. Please try again.";
        try {
          const body = (await res.json()) as {
            detail?: string;
            message?: string;
            error?: string;
            phoneNumber?: string;
          };
          message = body.detail || body.message || message;
          if (body.error === "duplicate" && body.phoneNumber) {
            message = body.detail || `A member with these details already exists. Use ${body.phoneNumber} to check in.`;
          }
        } catch {
          // Ignore JSON parsing errors and keep default message.
        }
        throw new Error(message);
      }

      const data = (await res.json()) as { ok: boolean; message: string; checkinCode?: string };
      setFirstName("");
      setLastName("");
      setEmail("");
      setPhoneNumber("");
      setGender("male");
      setMaritalStatus("single");
      setIsWorker(false);
      setDepartment(DEFAULT_DEPARTMENT_OPTIONS[0]);
      setCustomDepartment("");
      setServiceType("sunday_service");
      setConnectName(connectOptions[0] ?? DEFAULT_CONNECT_OPTIONS[0]);
      setNotice({
        type: "success",
        text: `${data.message} Redirecting...`,
      });
      setTimeout(() => router.push("/"), 1200);
    } catch (err) {
      const text = err instanceof Error ? err.message : "Registration failed";
      setNotice({ type: "error", text });
      void reportIssue({
        kind: "registration",
        message: text,
        httpStatus,
        details: {
          first_name: firstName,
          last_name: lastName,
          email,
          phone_number: phoneNumber,
          gender,
          marital_status: maritalStatus,
          is_worker: isWorker,
          department: selectedDepartment,
          service_type: serviceType,
          connect_name: showConnect ? connectName : null,
        },
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
          <h1 className={styles.title}>Check-in & Registration</h1>
          <p className={styles.subtitle}>
            Already a member? Use the <strong>Check-in</strong> tab to mark your attendance. New to our church? Use the <strong>Registration</strong> tab.
          </p>
        </header>

        <nav className={styles.tabs}>
          <button
            onClick={() => switchTab("checkin")}
            className={`${styles.tabButton} ${activeTab === "checkin" ? styles.tabButtonActive : ""}`}
          >
            Check-in
          </button>
          <button
            onClick={() => switchTab("register")}
            className={`${styles.tabButton} ${activeTab === "register" ? styles.tabButtonActive : ""}`}
          >
            New Member Registration
          </button>
        </nav>

        <section className={styles.card} style={{ padding: activeTab === "checkin" ? 0 : 22, overflow: "hidden" }}>
          {activeTab === "checkin" ? (
            <ChatWidget
              apiUrl="/api/checkin"
              welcomeMessage={`Hi! 👋 I'm here to help you check in for service.\n\n Please type your phone number to get started (e.g. 08012345678).\n\n`}
              containerStyle={{ minHeight: "0px", padding: 0 }}
            />
          ) : (
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
                  <span className={styles.label}>Are you a worker?</span>
                  <select
                    value={isWorker ? "yes" : "no"}
                    onChange={(e) => setIsWorker(e.target.value === "yes")}
                    className={styles.control}
                  >
                    <option value="no">No</option>
                    <option value="yes">Yes</option>
                  </select>
                </label>
              )}

              {showDepartment && (
                <label className={styles.field}>
                  <span className={styles.label}>Department</span>
                  <select value={department} onChange={(e) => setDepartment(e.target.value)} className={styles.control}>
                    {departmentOptions.map((option) => (
                      <option key={option} value={option}>
                        {option}
                      </option>
                    ))}
                  </select>
                </label>
              )}

              {showDepartment && department === "Others" && (
                <label className={styles.field}>
                  <span className={styles.label}>Custom department</span>
                  <input
                    required
                    value={customDepartment}
                    onChange={(e) => setCustomDepartment(e.target.value)}
                    className={styles.control}
                  />
                </label>
              )}

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
          )}
        </section>
      </div>
    </main>
  );
}

export default function RegisterPage() {
  return (
    <Suspense fallback={null}>
      <RegisterPageContent />
    </Suspense>
  );
}
