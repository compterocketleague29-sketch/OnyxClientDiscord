'use client'

import { useEffect } from 'react'
import { clearCart } from '@/app/actions/cart'

// Server Components cannot write cookies, so the paid cart is cleared from the client.
export function ClearCartOnMount() {
  useEffect(() => {
    void clearCart()
  }, [])
  return null
}
