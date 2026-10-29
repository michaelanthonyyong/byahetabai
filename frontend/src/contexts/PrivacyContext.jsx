import { createContext, useContext, useEffect, useState } from "react";

const KEY = "btb-agent-privacy-mode";
const PrivacyContext = createContext({ hidden: false, setHidden: () => {} });

export function PrivacyProvider({ children }) {
  const [hidden, setHidden] = useState(() => localStorage.getItem(KEY) === "1");
  useEffect(() => {
    localStorage.setItem(KEY, hidden ? "1" : "0");
  }, [hidden]);
  return (
    <PrivacyContext.Provider value={{ hidden, setHidden }}>{children}</PrivacyContext.Provider>
  );
}

export const usePrivacy = () => useContext(PrivacyContext);
