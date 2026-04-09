'use client';
import { useEffect } from 'react';
import { useRouter } from 'next/navigation';

export default function Home() {
  const router = useRouter();
  useEffect(() => {
    const t = typeof window !== 'undefined' ? localStorage.getItem('token') : null;
    router.replace(t ? '/dashboard' : '/login');
  }, [router]);
  return <div className="p-10 text-center">Yüklənir...</div>;
}
