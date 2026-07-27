This is a [Next.js](https://nextjs.org) project bootstrapped with [`create-next-app`](https://nextjs.org/docs/app/api-reference/cli/create-next-app).

## Getting Started

First, run the development server:

```bash
npm run dev
# or
yarn dev
# or
pnpm dev
# or
bun dev
```

Open [http://localhost:3000](http://localhost:3000) with your browser to see the result.

You can start editing the page by modifying `app/page.tsx`. The page auto-updates as you edit the file.

This project uses [`next/font`](https://nextjs.org/docs/app/building-your-application/optimizing/fonts) to automatically optimize and load [Geist](https://vercel.com/font), a new font family for Vercel.

## Prisma Migrations

This frontend now uses Prisma with a baseline migration in `prisma/migrations/20260727_init`.

- The existing database schema is treated as the starting point.
- For new schema changes, update `prisma/schema.prisma` and run `npm run prisma:migrate:dev -- --name your_change_name`.
- In deployment environments, apply committed migrations with `npm run prisma:migrate:deploy`.
- `npm run prisma:db:push` is available for local-only syncs, but migrations should be the default for shared environments.

## Learn More

To learn more about Next.js, take a look at the following resources:

- [Next.js Documentation](https://nextjs.org/docs) - learn about Next.js features and API.
- [Learn Next.js](https://nextjs.org/learn) - an interactive Next.js tutorial.

You can check out [the Next.js GitHub repository](https://github.com/vercel/next.js) - your feedback and contributions are welcome!

## Deploy on Vercel

The easiest way to deploy your Next.js app is to use the [Vercel Platform](https://vercel.com/new?utm_medium=default-template&filter=next.js&utm_source=create-next-app&utm_campaign=create-next-app-readme) from the creators of Next.js.

Check out our [Next.js deployment documentation](https://nextjs.org/docs/app/building-your-application/deploying) for more details.

## GitHub Production Deploy

This repo now includes a production workflow at [`.github/workflows/deploy-frontend-prod.yml`](../.github/workflows/deploy-frontend-prod.yml).

It deploys `frontend/` to Vercel when:

- code is pushed to the `main` branch, and
- the pushed changes touch `frontend/**` or the workflow file itself

It can also be run manually from GitHub Actions with `workflow_dispatch`.

### Required GitHub Secrets

Add these repository secrets before enabling the workflow:

- `VERCEL_DEPLOY_HOOK_URL`
- `FRONTEND_DATABASE_URL`
- `FRONTEND_OPENAI_API_KEY`
- `FRONTEND_ADMIN_API_KEY`
- `FRONTEND_URL`

Optional secrets:

- `FRONTEND_OPENAI_CHAT_MODEL`
- `FRONTEND_OPENAI_EMBED_MODEL`
- `FRONTEND_DEFAULT_PHONE_REGION`

### Notes

- The workflow runs `npm run prisma:migrate:deploy` before building, so production uses committed Prisma migrations.
- App runtime environment variables still need to exist in Vercel as well, because the deploy hook only tells Vercel to build and deploy the latest connected commit.
- A deploy hook is narrower in scope than a general Vercel API token, which makes it a cleaner secret when all you need is “deploy this project now”.
- If you prefer AWS/EC2 deployment instead of Vercel, we can swap this workflow to build and ship a Docker image to your existing infrastructure.
