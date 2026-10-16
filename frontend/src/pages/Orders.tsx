import { useState } from "react";
import { Package, ReceiptText } from "lucide-react";
import { useRemote } from "../lib/hooks";
import { ErrorBox, Empty, Modal, Pagination } from "../components/ui";
import { money, options, orderStatus, type Order } from "../store/api";
export function OrdersPage({ revision }: { revision: number }) {
  const [page, setPage] = useState(1),
    [selected, setSelected] = useState<Order | null>(null);
  const { data, error, loading } = useRemote<{ items: Order[]; total: number }>(
    "/orders?page=" + page,
    revision,
  );
  return (
    <>
      <section className="panel">
        <div className="panel-heading">
          <div>
            <h3>Đơn hàng COD</h3>
            <p>Đơn thử nghiệm được tạo từ storefront.</p>
          </div>
          <ReceiptText size={20} />
        </div>
        <ErrorBox message={error} />
        <div className="table-scroll">
          <table>
            <thead>
              <tr>
                <th>MÃ ĐƠN</th>
                <th>KHÁCH HÀNG</th>
                <th>TỔNG TIỀN</th>
                <th>TRẠNG THÁI</th>
                <th />
              </tr>
            </thead>
            <tbody>
              {data?.items.map((o) => (
                <tr key={o.id}>
                  <td>
                    <button
                      className="text-button"
                      onClick={() => setSelected(o)}
                    >
                      {o.code}
                    </button>
                    <small style={{ display: "block", fontSize: 9 }}>
                      {new Date(o.created_at).toLocaleString("vi-VN")}
                    </small>
                  </td>
                  <td>
                    {o.customer_name}
                    <small
                      style={{ display: "block", fontSize: 9, marginTop: 5 }}
                    >
                      {o.phone}
                    </small>
                  </td>
                  <td>{money(o.total)}</td>
                  <td>
                    <span className="badge pending">
                      <span />
                      {orderStatus[o.status] || o.status}
                    </span>
                  </td>
                  <td>
                    <button
                      className="text-button"
                      onClick={() => setSelected(o)}
                    >
                      Chi tiết
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        {!loading && data?.items.length === 0 && (
          <Empty
            text="Chưa có đơn hàng"
            hint="Đơn hàng khách đặt trên storefront sẽ hiển thị tại đây."
          />
        )}
        <Pagination page={page} total={data?.total || 0} onChange={setPage} />
      </section>
      {selected && (
        <Modal
          title={"Đơn " + selected.code}
          subtitle={orderStatus[selected.status] || selected.status}
          onClose={() => setSelected(null)}
          wide
        >
          <div className="modal-body">
            <p style={{ lineHeight: 2, marginBottom: 20 }}>
              <strong>{selected.customer_name}</strong> · {selected.phone}
              <br />
              {selected.address}
              {selected.note && (
                <>
                  <br />
                  Ghi chú: {selected.note}
                </>
              )}
            </p>
            <div className="table-scroll">
              <table>
                <thead>
                  <tr>
                    <th>SẢN PHẨM</th>
                    <th>SỐ LƯỢNG</th>
                    <th>ĐƠN GIÁ</th>
                  </tr>
                </thead>
                <tbody>
                  {selected.items.map((item, i) => (
                    <tr key={i}>
                      <td>
                        {item.name}
                        <small style={{ display: "block", marginTop: 6 }}>
                          {item.sku} · {options(item.options)}
                        </small>
                      </td>
                      <td>{item.quantity}</td>
                      <td>{money(item.unit_price)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <p style={{ textAlign: "right", lineHeight: 2, marginTop: 20 }}>
              Phí giao hàng: {money(selected.shipping_fee)}
              <br />
              <strong>Tổng COD: {money(selected.total)}</strong>
            </p>
          </div>
        </Modal>
      )}
    </>
  );
}
