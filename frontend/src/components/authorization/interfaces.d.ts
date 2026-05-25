export interface IAuthorizationService {
    id: string;
    label: string;
    icon: string;
    action: Function;
}
export type TAuthorizationWrapperProps = {
    title: string;
    subTitle?: string;
    image: string;
    hideSso?: boolean;
};
