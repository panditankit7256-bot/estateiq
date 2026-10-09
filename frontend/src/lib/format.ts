export const num = (n: number | null | undefined, d = 0) => (n == null || Number.isNaN(n) ? "-" : n.toLocaleString("en-IN", { maximumFractionDigits: d, minimumFractionDigits: d }));
export const inr = (n: number | null | undefined) => (n == null ? "-" : "₹" + Math.round(n).toLocaleString("en-IN"));
export const compact = (n: number) => (Math.abs(n) >= 1e5 ? (n / 1e5).toFixed(1) + " lakh" : Math.abs(n) >= 1e3 ? (n / 1e3).toFixed(1) + "k" : String(Math.round(n)));
export const day = (iso: string) => new Date(iso).toLocaleDateString("en-IN", { day: "numeric", month: "short" });
export const dt = (iso: string) => new Date(iso).toLocaleString("en-IN", { day: "numeric", month: "short", hour: "2-digit", minute: "2-digit" });
export const hour = (h: number) => `${String(h).padStart(2, "0")}:00`;
