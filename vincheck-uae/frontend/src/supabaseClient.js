import { createClient } from '@supabase/supabase-js';

// These come from your Supabase project dashboard → Settings → API.
// Set them in a .env file at the project root (same folder as package.json):
//
//   VITE_SUPABASE_URL=https://your-project.supabase.co
//   VITE_SUPABASE_ANON_KEY=your-anon-key-here
//
// Vite only exposes env vars prefixed with VITE_ to the browser — this is
// intentional and required, plain SUPABASE_URL would not be visible here.

const supabaseUrl = import.meta.env.VITE_SUPABASE_URL;
const supabaseAnonKey = import.meta.env.VITE_SUPABASE_ANON_KEY;

if (!supabaseUrl || !supabaseAnonKey) {
  console.warn(
    'Supabase env vars missing. Auth and history will not work until ' +
    'VITE_SUPABASE_URL and VITE_SUPABASE_ANON_KEY are set in a .env file.'
  );
}

export const supabase = createClient(supabaseUrl || '', supabaseAnonKey || '');
