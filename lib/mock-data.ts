export type ModuleNode = {
  id: string;
  title: string;
  subtitle: string;
  x: number;
  y: number;
  locked?: boolean;
  current?: boolean;
};

export const roadmapModules: ModuleNode[] = [
  { id: "hola-vecino", title: "Hola vecino", subtitle: "Short introductions", x: 24, y: 78 },
  { id: "vida-diaria", title: "Vida diaria", subtitle: "Family, routines, basics", x: 39, y: 64, current: true },
  { id: "invitaciones", title: "Invitaciones", subtitle: "Plans and follow-ups", x: 54, y: 49 },
  { id: "problemas", title: "Problemas", subtitle: "Clarifying and help", x: 67, y: 37, locked: true },
  { id: "comodidad", title: "Comodidad", subtitle: "Longer natural exchanges", x: 78, y: 23, locked: true },
];

export const todaysWords = ["vecino", "cocinar", "calle", "tiempo libre"];

export const messages = [
  {
    role: "assistant" as const,
    content:
      "Hola. Soy tu vecina nueva. Vivo en la casa azul. ¿Qué te gusta hacer en tu tiempo libre?",
  },
  {
    role: "user" as const,
    content: "Me gusta cocinar con mi familia y caminar en la calle.",
  },
  {
    role: "assistant" as const,
    content: "Qué bien. Yo también cocino mucho. ¿Qué comida te gusta preparar?",
  },
];
