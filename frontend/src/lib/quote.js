import { api, formatApiError } from "@/lib/api";

async function blobError(err) {
  const data = err?.response?.data;
  if (data instanceof Blob) {
    try {
      const json = JSON.parse(await data.text());
      return formatApiError({ response: { data: json } });
    } catch {
      return "Could not generate the PDF.";
    }
  }
  return formatApiError(err);
}

function saveBlob(blob, filename) {
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  a.remove();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}

const filenameFrom = (res, fallback) =>
  /filename="([^"]+)"/.exec(res.headers?.["content-disposition"] || "")?.[1] || fallback;

/** Download a PDF from the agent API. Returns null on success or an error message. */
export async function downloadQuote({ method = "post", url, body }) {
  try {
    const res = method === "post"
      ? await api.post(url, body, { responseType: "blob" })
      : await api.get(url, { responseType: "blob" });
    saveBlob(res.data, filenameFrom(res, "quote.pdf"));
    return null;
  } catch (err) {
    return blobError(err);
  }
}
