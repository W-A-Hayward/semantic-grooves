import React from "react"
import type { Metadata } from 'next'
import { JetBrains_Mono } from 'next/font/google'

import './globals.css'

const jetbrains = JetBrains_Mono({
  subsets: ['latin'],
  variable: '--font-jetbrains',
})

export const metadata: Metadata = {
  title: 'CRATESEARCH // Pitchfork Review Discovery',
  description: 'A hybrid search engine for discovering music through Pitchfork album reviews. Semantic + lexical search across thousands of reviews.',
}

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode
}>) {
  return (
    <html lang="en" className={jetbrains.variable}>
      <body className="font-mono antialiased">{children}</body>
    </html>
  )
}
