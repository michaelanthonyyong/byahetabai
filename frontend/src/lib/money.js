/** Public-site currency formatter. PHP for V1. */
export function formatPHP(value) {
  if (value === null || value === undefined || value === "") return "";
  const n = typeof value === "number" ? value : parseFloat(value);
  if (Number.isNaN(n)) return "";
  return new Intl.NumberFormat("en-PH", {
    style: "currency",
    currency: "PHP",
    maximumFractionDigits: 0,
  }).format(n);
}
