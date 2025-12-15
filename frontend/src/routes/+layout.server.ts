import { redirect } from '@sveltejs/kit';
import type { LayoutServerLoad } from './$types';

export const load: LayoutServerLoad = async ({ url }) => {
	// Le verifiche di autenticazione vengono fatte lato client
	// perché il token è in localStorage
	return {};
};

