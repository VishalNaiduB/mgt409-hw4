import { useState, type FormEvent } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { useAuth, type SignupData } from '../auth'

const EMPTY: SignupData = { first_name: '', last_name: '', email: '', password: '', confirm_password: '' }

export default function CreateAccount() {
  const { signup } = useAuth()
  const navigate = useNavigate()
  const [form, setForm] = useState<SignupData>(EMPTY)
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)

  const field = (key: keyof SignupData) => ({
    value: form[key],
    onChange: (e: React.ChangeEvent<HTMLInputElement>) => setForm({ ...form, [key]: e.target.value }),
    required: true,
  })

  async function onSubmit(e: FormEvent) {
    e.preventDefault()
    setError('')
    if (form.password !== form.confirm_password) {
      setError('Passwords do not match.')
      return
    }
    setBusy(true)
    try {
      await signup(form)
      navigate('/')
    } catch (err) {
      setError((err as Error).message)
    } finally {
      setBusy(false)
    }
  }

  return (
    <section className="page auth-page">
      <h1>Create account</h1>
      <form className="auth-form" onSubmit={onSubmit}>
        <div className="form-row">
          <label>First name<input autoComplete="given-name" {...field('first_name')} /></label>
          <label>Last name<input autoComplete="family-name" {...field('last_name')} /></label>
        </div>
        <label>Email<input type="email" autoComplete="email" {...field('email')} /></label>
        <label>Password<input type="password" autoComplete="new-password" minLength={8} {...field('password')} /></label>
        <label>Confirm password<input type="password" autoComplete="new-password" minLength={8} {...field('confirm_password')} /></label>
        {error && <p className="form-error" role="alert">{error}</p>}
        <button type="submit" disabled={busy}>{busy ? 'Creating account…' : 'Create account'}</button>
      </form>
      <p className="muted">Already have an account? <Link to="/login">Log in</Link></p>
    </section>
  )
}
