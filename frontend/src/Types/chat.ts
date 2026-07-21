interface Citation {
  index: number;
  title?: string;
  filename?: string;
  url?: string;
  snippet: string;
}

interface Message {
  id: string;
  role: "user" | "assistant";
  content: string;
  citations?: Citation[];
  toolsUsed?: string[];
  isStreaming?: boolean;
}

interface ApiMessage {
  id: string;
  role: "user" | "assistant";
  content: string;
  citations?: string | null;
  tools_used?: string[];
}

interface Props {
  currentConvId: string | null;
  setCurrentConvId: (id: string | null) => void;
  onNewConversation: () => void;
  onOpenSidebar: () => void;
  onMessageComplete?: () => void;
}

interface ChatInputProps {
  input: string;
  setInput: (val: string) => void;
  loading: boolean;
  webSearch: boolean;
  setWebSearch: React.Dispatch<React.SetStateAction<boolean>>;
  ragSearch: boolean;
  setRagSearch: React.Dispatch<React.SetStateAction<boolean>>;
  onKeyDown: (e: React.KeyboardEvent) => void;
  onSend: () => void;
  placeholder?: string;
  maxWClass?: string;
}

export type { Citation, ApiMessage, Props, Message, ChatInputProps}