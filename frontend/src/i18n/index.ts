import i18n from "i18next";
import { initReactI18next } from "react-i18next";

const en = {
  nav: { command: "Command centre", air: "Air quality", energy: "Energy", water: "Water", waste: "Waste", traffic: "Traffic and parking", assets: "Assets", safety: "Safety", emissions: "Emissions and climate", scorecard: "Scorecard", scenarios: "Scenario simulator", insights: "Insights and actions", settings: "Settings and assumptions" },
  disclaimer: "Decision-support insight, not an official measurement",
  signOut: "Sign out", signIn: "Sign in", facility: "Facility", window: "Time window", days: "days",
  kpi: { aqi: "Air quality (24 h)", energy: "Energy (24 h)", cost: "Grid cost (24 h)", water: "Water (24 h)", bins: "Bins to collect", incidents: "Open incidents", co2: "CO2 (24 h)" },
};
const hi = {
  nav: { command: "कमांड सेंटर", air: "वायु गुणवत्ता", energy: "ऊर्जा", water: "जल", waste: "कचरा", traffic: "ट्रैफिक और पार्किंग", assets: "उपकरण", safety: "सुरक्षा", emissions: "उत्सर्जन और जलवायु", scorecard: "स्कोरकार्ड", scenarios: "परिदृश्य सिम्युलेटर", insights: "सुझाव और कार्य", settings: "सेटिंग और मान्यताएँ" },
  disclaimer: "निर्णय-सहायक संकेत, आधिकारिक माप नहीं",
  signOut: "साइन आउट", signIn: "साइन इन", facility: "सुविधा", window: "समय अवधि", days: "दिन",
  kpi: { aqi: "वायु गुणवत्ता (24 घं.)", energy: "ऊर्जा (24 घं.)", cost: "ग्रिड लागत (24 घं.)", water: "जल (24 घं.)", bins: "खाली करने वाले डिब्बे", incidents: "खुली घटनाएँ", co2: "CO2 (24 घं.)" },
};
i18n.use(initReactI18next).init({ resources: { en: { translation: en }, hi: { translation: hi } }, lng: "en", fallbackLng: "en", interpolation: { escapeValue: false } });
export default i18n;
