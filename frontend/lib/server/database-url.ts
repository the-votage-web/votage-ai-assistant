export function getDatabaseUrl() {
  const direct = process.env.DATABASE_URL?.trim();
  if (direct) {
    return direct;
  }

  const user = process.env.DB_USER?.trim();
  const password = process.env.DB_PASSWORD?.trim();
  const host = process.env.DB_HOST?.trim();
  const name = process.env.DB_NAME?.trim();
  const port = process.env.DB_PORT?.trim() || "5432";

  if (!user || !password || !host || !name) {
    throw new Error("DATABASE_URL or DB_* environment variables are required.");
  }

  const params = new URLSearchParams();
  const sslMode = process.env.DB_SSLMODE?.trim();
  const options = process.env.DB_OPTIONS?.trim();
  const channelBinding = process.env.DB_CHANNEL_BINDING?.trim();

  if (sslMode) params.set("sslmode", sslMode);
  if (options) params.set("options", options);
  if (channelBinding) params.set("channel_binding", channelBinding);

  const query = params.toString();
  const authUser = encodeURIComponent(user);
  const authPassword = encodeURIComponent(password);
  const base = `postgresql://${authUser}:${authPassword}@${host}:${port}/${name}`;
  return query ? `${base}?${query}` : base;
}
