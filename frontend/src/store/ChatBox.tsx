import { type FormEvent, useEffect, useRef, useState } from "react";
import {
  ArrowUp,
  ArrowUpRight,
  MessageCircle,
  RotateCcw,
  Sparkles,
  X,
} from "lucide-react";
import { ChatResponse, Product, image, money, shopApi } from "./api";
type Turn = {
  role: "user" | "assistant";
  content: string;
  products?: Product[];
  sources?: ChatResponse["sources"];
  degraded?: boolean;
};
export function ChatBox({
  open,
  onToggle,
  onProduct,
  onPolicy,
}: {
  open: boolean;
  onToggle: () => void;
  onProduct: (p: Product) => void;
  onPolicy: (id: string) => void;
}) {
  const [messages, setMessages] = useState<Turn[]>([]),
    [input, setInput] = useState(""),
    [busy, setBusy] = useState(false),
    [error, setError] = useState(""),
    end = useRef<HTMLDivElement>(null),
    field = useRef<HTMLInputElement>(null);
  useEffect(() => {
    if (open) field.current?.focus();
  }, [open]);
  useEffect(() => {
    if (open) end.current?.scrollIntoView({ block: "nearest" });
  }, [messages, busy, open]);
  async function send(text: string, retry = false) {
    if (busy || !text.trim()) return;
    setError("");
    const history = retry
      ? messages
      : [...messages, { role: "user" as const, content: text.trim() }];
    setMessages(history);
    setInput("");
    setBusy(true);
    try {
      const response = await shopApi<ChatResponse>("/chat", "POST", {
        messages: history
          .slice(-9)
          .map((m) => ({ role: m.role, content: m.content.slice(0, 1500) })),
      });
      setMessages([
        ...history,
        {
          role: "assistant",
          content: response.message,
          products: response.products,
          sources: response.sources,
          degraded: response.degraded,
        },
      ]);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }
  function submit(e: FormEvent) {
    e.preventDefault();
    send(input);
  }
  return (
    <div className="shop-chat-root">
      {open && (
        <section className="shop-chat-window" aria-label="Trợ lý mua sắm">
          <header>
            <span className="shop-chat-avatar">
              <Sparkles size={21} />
            </span>
            <div>
              <strong>Trợ lý mua sắm</strong>
              <small>Giúp bạn tìm đôi giày phù hợp</small>
            </div>
            <button onClick={onToggle} aria-label="Thu nhỏ khung chat">
              <X size={20} />
            </button>
          </header>
          <div className="shop-chat-messages" aria-live="polite">
            <div className="shop-chat-welcome">
              <span>
                <Sparkles size={23} />
              </span>
              <h3>Chào bạn, mình có thể giúp gì?</h3>
              <p>
                Kể mình nghe về nhu cầu của bạn. Mình sẽ tìm trong sản phẩm và
                chính sách của cửa hàng.
              </p>
            </div>
            {!messages.length && (
              <div className="shop-chat-suggestions">
                {[
                  "Tìm giày đi bộ đế êm",
                  "Tư vấn giày chạy bộ",
                  "Chính sách đổi trả thế nào?",
                ].map((q) => (
                  <button key={q} onClick={() => send(q)}>
                    {q}
                    <ArrowUpRight size={14} />
                  </button>
                ))}
              </div>
            )}
            {messages.map((m, i) => (
              <div className={"shop-chat-turn " + m.role} key={i}>
                <div className="shop-chat-bubble">{m.content}</div>
                {m.products?.map((p) => (
                  <button
                    className="shop-chat-product"
                    key={p.id}
                    onClick={() => onProduct(p)}
                  >
                    <img
                      src={image(p.category_slug)}
                      alt="Ảnh minh họa sản phẩm"
                    />
                    <span>
                      <strong>{p.name}</strong>
                      <small>
                        {money(p.min_price)}
                        {p.stock === 0 ? " · Hết hàng" : ""}
                      </small>
                    </span>
                    <ArrowUpRight size={15} />
                  </button>
                ))}
                {m.sources && m.sources.length > 0 && (
                  <div className="shop-chat-sources">
                    <span>Thông tin tham khảo</span>
                    {m.sources.map((s) => (
                      <button
                        key={s.id}
                        onClick={() =>
                          s.type === "product"
                            ? shopApi<Product>("/products/" + s.id)
                                .then(onProduct)
                                .catch(() =>
                                  setError("Sản phẩm không còn được hiển thị."),
                                )
                            : onPolicy(s.id)
                        }
                      >
                        {s.title}
                        <ArrowUpRight size={11} />
                      </button>
                    ))}
                  </div>
                )}
              </div>
            ))}
            {busy && (
              <div className="shop-chat-thinking">
                <i />
                <i />
                <i />
                <span>Đang tìm thông tin cho bạn…</span>
              </div>
            )}
            {error && (
              <div className="shop-chat-error" role="alert">
                <p>{error}</p>
                <button
                  onClick={() =>
                    send(messages[messages.length - 1]?.content || "", true)
                  }
                >
                  <RotateCcw size={13} />
                  Thử lại
                </button>
              </div>
            )}
            <div ref={end} />
          </div>
          <form onSubmit={submit}>
            <input
              ref={field}
              aria-label="Tin nhắn cho trợ lý"
              maxLength={1500}
              placeholder="Bạn đang tìm đôi giày như thế nào?"
              value={input}
              onChange={(e) => setInput(e.target.value)}
              disabled={busy}
            />
            <button aria-label="Gửi tin nhắn" disabled={busy || !input.trim()}>
              <ArrowUp size={19} />
            </button>
          </form>
          <div className="shop-chat-disclaimer">
            Trợ lý AI có thể nhầm lẫn. Kiểm tra thông tin trước khi đặt hàng.
          </div>
        </section>
      )}
      <button
        className={"shop-chat-launch " + (open ? "opened" : "")}
        onClick={onToggle}
        aria-label={open ? "Đóng trợ lý mua sắm" : "Mở trợ lý mua sắm"}
      >
        {open ? (
          <X size={22} />
        ) : (
          <>
            <MessageCircle size={23} />
            <span>Hỏi trợ lý</span>
            <i />
          </>
        )}
      </button>
    </div>
  );
}
