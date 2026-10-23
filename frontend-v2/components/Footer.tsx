import Icon from "./Icon";

export default function Footer() {
  return (
    <footer className="site-footer">
      <div className="site-footer-inner">
        <div>
          <div className="footer-brand">
            <Icon name="fork" size={18} className="accent" />
            <span className="text-label-lg">Bangalore Culinary Pulse</span>
          </div>
          <p className="text-body-sm muted" style={{ margin: "0.3rem 0 0" }}>
            AI-synthesized dining intelligence for Bangalore, built on a real Zomato catalog.
          </p>
        </div>
      </div>
    </footer>
  );
}
