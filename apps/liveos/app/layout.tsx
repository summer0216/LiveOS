import type { Metadata } from 'next';
import './styles.css';

export const metadata: Metadata = {
  title: 'LiveOS',
  description: 'Conversation for better decisions about how you live.',
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="zh-CN">
      <body>{children}</body>
    </html>
  );
}
