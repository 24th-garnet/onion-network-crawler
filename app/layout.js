import "./globals.css";

export const metadata = {
  title: "Onion Network Dashboard",
  description: "Tor-based onion graph crawler web console"
};

export default function RootLayout({ children }) {
  return (
    <html lang="ja">
      <body>{children}</body>
    </html>
  );
}
