import "./globals.css";
import Navbar from "../components/Navbar";

export const metadata = {
  title: "Threads Contest Engine",
  description: "Threads Contest Engine MVP",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <body>
        <Navbar />
        <main className="min-h-screen px-6 pb-24 pt-6">{children}</main>
      </body>
    </html>
  );
}
