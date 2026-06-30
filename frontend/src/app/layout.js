import "./globals.css";

export const metadata = {
  title: "DocsChat — Talk to your Documents",
  description: "AI-powered document assistant. Upload PDFs, Docs, TXT and get instant, grounded answers.",
};

export default function RootLayout({ children }) {
  return (
    <html lang="en" data-scroll-behavior="smooth" suppressHydrationWarning>
      <head>
        <link rel="preconnect" href="https://fonts.googleapis.com" />
        <link rel="preconnect" href="https://fonts.gstatic.com" crossOrigin="anonymous" />
        <link
          href="https://fonts.googleapis.com/css2?family=Lora:ital,wght@0,400;0,600;0,700;1,400;1,600&family=Outfit:wght@300;400;500;600;700&family=Plus+Jakarta+Sans:wght@300;400;500;600;700;800&family=JetBrains+Mono:wght@400;500&display=swap"
          rel="stylesheet"
        />
        <script
          dangerouslySetInnerHTML={{
            __html: `
              (function() {
                try {
                  var color = localStorage.getItem('app_theme_color') || 'emerald';
                  var mode = localStorage.getItem('app_theme_mode') || 'light';
                  document.documentElement.setAttribute('data-theme', color);
                  document.documentElement.setAttribute('data-mode', mode);
                } catch (e) {}
              })();
            `,
          }}
        />
      </head>
      <body className="grain">{children}</body>
    </html>
  );
}
