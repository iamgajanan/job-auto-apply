-- Seed the initial super-admin allowlist.
-- Supabase Auth remains responsible for credentials and sessions.
-- Admin role assignment is performed by the backend after authentication.

insert into public.admin_allowlist (email, is_active)
values
  ('iamgajanan12@gmail.com', true),
  ('gajushinde8046@gmail.com', true),
  ('iamgajanan@yopmail.com', true),
  ('iamgajanan1@gmail.com', true),
  ('iamgajanan3@gmail.com', true)
on conflict (email) do update
set is_active = excluded.is_active;
